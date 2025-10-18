"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet, Users, Percent, BarChart, Clock } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import MAVCModal from "./MAVCModal";
import api from "@/lib/api";

interface MAVPStrategyCardProps {
  onRefresh?: () => void;
}

const MAVPStrategyCard: React.FC<MAVPStrategyCardProps> = ({ onRefresh }) => {
  const router = useRouter();
  const [mavpBalance, setMavpBalance] = useState("0");
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);

  const mockData = {
    name: "Multi Asset Vault Protocol",
    description: "Advanced yield farming protocol with automated rebalancing and risk management.",
    netApy: 89.7,
    aum: 15.2,
    sharpe: 1.45,
    maxDrawdown: 28.3,
    lockInPeriod: "7d",
    participants: 342,
    performanceFee: 15.0,
  };

  useEffect(() => {
    fetchBalances();
  }, []);

  const fetchBalances = async () => {
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        if (parsedData.wallet_address) {
          try {
            const mavpResponse = await api.get(`/api/v1/mavp/balance/${parsedData.wallet_address}`);
            setMavpBalance(mavpResponse.data.balance || "0");
          } catch (err) {
            console.warn('MAVP balance not available:', err);
            setMavpBalance("0");
          }
          
          try {
            const usdcResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            const usdcBalance = usdcResponse.data.balances?.find((b: any) => b.token.symbol === 'USDC')?.amount || "0";
            setUsdcBalance(usdcBalance);
          } catch (err) {
            console.warn('USDC balance not available:', err);
            setUsdcBalance("0");
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
      
      const approveResponse = await api.post('/api/v1/mavp/approve', payload);
      
      if (approveResponse.data.status !== 'success') {
        throw new Error('USDC approval failed');
      }
      
      setTransactionSuccess(`Approval submitted! Now depositing...`);
      
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const response = await api.post('/api/v1/mavp/deposit', payload);
      
      if (response.data.status === 'success') {
        setTransactionSuccess(`Successfully deposited ${amount} USDC to MAVP!`);
        
        if (onRefresh) onRefresh();
        setTimeout(() => {
          fetchBalances();
        }, 1000);
      } else {
        throw new Error(response.data.message || 'Deposit failed');
      }
    } catch (err: any) {
      console.error('MAVP Deposit Error:', err);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to deposit to MAVP vault';
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
      
      const response = await api.post('/api/v1/mavp/withdraw', payload);
      
      if (response.data.status === 'success') {
        setTransactionSuccess(`Successfully withdrew ${amount} MAVP tokens!`);
        
        if (onRefresh) onRefresh();
        setTimeout(() => {
          fetchBalances();
        }, 1000);
      } else {
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('MAVP Withdraw Error:', err);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to withdraw from MAVP vault';
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
    router.push('/customer/grow/hedge-fund-v2/mavp');
  };

  const formatBalance = (balance: string): string => {
    try {
      const numBalance = parseFloat(balance) / 1e12;
      if (isNaN(numBalance) || numBalance === 0) return '0';
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
            <div className="flex items-center gap-2 bg-blue-500/20 text-blue-300 px-3 py-1 rounded-lg border border-blue-500/30">
              <Wallet className="w-4 h-4" />
              <span className="text-sm font-semibold">{formatBalance(mavpBalance)} MAVP</span>
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
        mavcBalance={mavpBalance}
        onDeposit={handleDeposit}
        onWithdraw={handleWithdraw}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
      />
    </>
  );
};

export default MAVPStrategyCard;
