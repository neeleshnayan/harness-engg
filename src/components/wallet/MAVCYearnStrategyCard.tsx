"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet, Users, Percent, BarChart, Clock, Shield } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn, formatTokenBalance } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";
import { BalanceStatusIndicator, BalanceTransactionStage, BalanceTransactionType } from "./BalanceStatusIndicator";
import MAVCYearnModal from "./MAVCYearnModal";

interface MAVCYearnStrategyCardProps {
  onRefresh?: () => void;
}

const MAVCYearnStrategyCard: React.FC<MAVCYearnStrategyCardProps> = ({ onRefresh }) => {
  const router = useRouter();
  const { toast } = useToast();

  const [vaultBalance, setVaultBalance] = useState("0"); // Yearn vault shares
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);
  const [transactionStage, setTransactionStage] = useState<BalanceTransactionStage>('idle');
  const [transactionType, setTransactionType] = useState<BalanceTransactionType>('deposit');

  // Yearn-specific metrics
  const [vaultTotalAssets, setVaultTotalAssets] = useState(0);
  const [vaultPricePerShare, setVaultPricePerShare] = useState(1.0);

  // Strategy metrics for MAVC Yearn
  const strategyMetrics = {
    name: "MAVC Yearn",
    description: "Yearn v3 tokenized strategy with 50/50 USDC/BTC allocation using MAVC rebalancing logic.",
    netApy: 45.2, // Conservative APY for Yearn vault
    aum: 2.1, // Starting AUM
    aumUnit: 'M',
    sharpe: 1.12,
    maxDrawdown: 18.50,
    lockInPeriod: "None", // Yearn vaults typically have no lock-in
    participants: 34, // Initial participants
    performanceFee: 20.0, // Yearn standard performance fee
    riskGrade: "B" as const
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
        console.log('🔍 MAVC Yearn - User Data from localStorage:', parsedData);

        if (parsedData.wallet_address) {
          setWalletAddress(parsedData.wallet_address);

          try {
            console.log(`🔍 MAVC Yearn - Fetching wallet balances for: ${parsedData.wallet_address}`);
            const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            console.log('✅ MAVC Yearn - Wallet Balance Response:', walletResponse.data);

            if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
              // Find USDC tokens (merge TRNSK which is treated as USDC)
              const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
                b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
              );

              if (allUSDCTokens.length > 0) {
                const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                  return sum + parseFloat(token.amount || "0");
                }, 0);
                setUsdcBalance(totalUSDC.toString());
                console.log('✅ MAVC Yearn - USDC Balance set to:', totalUSDC);
              } else {
                setUsdcBalance("0");
              }

              // Fetch Yearn vault share balance from backend
              try {
                const yearnBalanceResponse = await api.get(`/api/v1/mavc-yearn/balance/${parsedData.wallet_address}`);
                console.log('✅ MAVC Yearn - Vault Balance Response:', yearnBalanceResponse.data);
                
                if (yearnBalanceResponse.data && yearnBalanceResponse.data.balance) {
                  setVaultBalance(yearnBalanceResponse.data.balance);
                  console.log('✅ MAVC Yearn - Vault Balance set to:', yearnBalanceResponse.data.balance);
                } else {
                  setVaultBalance("0");
                }
              } catch (err) {
                console.warn('❌ MAVC Yearn - Vault balance not available:', err);
                setVaultBalance("0");
              }
            } else {
              setUsdcBalance("0");
              setVaultBalance("0");
            }
          } catch (err) {
            console.warn('❌ MAVC Yearn - Wallet balances not available:', err);
            setUsdcBalance("0");
          }
          
          // Fetch vault balance separately
          try {
            const yearnBalanceResponse = await api.get(`/api/v1/mavc-yearn/balance/${parsedData.wallet_address}`);
            if (yearnBalanceResponse.data && yearnBalanceResponse.data.balance) {
              setVaultBalance(yearnBalanceResponse.data.balance);
            } else {
              setVaultBalance("0");
            }
          } catch (err) {
            console.warn('❌ MAVC Yearn - Vault balance fetch failed:', err);
            setVaultBalance("0");
          }
        }
      }
    } catch (err: any) {
      console.error('Error fetching MAVC Yearn balances:', err);
    }
  };

  const handleDeposit = async (amount: string) => {
    console.log('🚀 MAVC Yearn handleDeposit called with amount:', amount);

    setShowModal(false);

    try {
      setTransactionLoading(true);
      setTransactionError(null);
      setTransactionSuccess(null);
      setTransactionType('deposit');
      setTransactionStage('approving');

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

      // Capture initial balance before transaction
      const initialVaultBalance = parseFloat(vaultBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);

      console.log('🔍 STEP 1: Calling approve endpoint...');
      const approveResponse = await api.post('/api/v1/mavc-yearn/approve', payload);

      if (approveResponse.data.status !== 'success') {
        throw new Error('USDC approval failed');
      }

      const approveTxId = approveResponse.data.transaction_id;
      console.log('✅ Approval transaction submitted:', approveTxId);

      setTransactionStage('approved');
      await new Promise(resolve => setTimeout(resolve, 500));

      console.log('🔍 STEP 2: Calling deposit endpoint...');
      setTransactionStage('processing');

      const depositPayload = {
        ...payload,
        approve_tx_id: approveTxId
      };

      const response = await api.post('/api/v1/mavc-yearn/deposit', depositPayload);

      if (response.data.status === 'success') {
        console.log('✅ Deposit transaction created');
        setTransactionStage('confirming');

        // Poll for balance change
        const maxAttempts = 60;
        let attempts = 0;
        let balanceChanged = false;

        while (attempts < maxAttempts && !balanceChanged) {
          await new Promise(resolve => setTimeout(resolve, 2000));

          // Check vault balance directly from backend
          try {
            const yearnBalanceResponse = await api.get(`/api/v1/mavc-yearn/balance/${parsedData.wallet_address}`);
            
            if (yearnBalanceResponse.data && yearnBalanceResponse.data.balance) {
              const currentVaultBalance = parseFloat(yearnBalanceResponse.data.balance || "0");
              console.log(`🔍 Attempt ${attempts + 1}: Vault Balance = ${currentVaultBalance} (initial: ${initialVaultBalance})`);

              if (currentVaultBalance > initialVaultBalance) {
                console.log('✅ Balance changed!');
                balanceChanged = true;
                setTransactionStage('success');
                setVaultBalance(currentVaultBalance.toString());

                // Update USDC balance
                const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
                if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
                  const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
                    b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
                  );
                  if (allUSDCTokens.length > 0) {
                    const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                      return sum + parseFloat(token.amount || "0");
                    }, 0);
                    setUsdcBalance(totalUSDC.toString());
                  }
                }

                setTransactionSuccess(`Successfully deposited ${amount} USDC to MAVC Yearn vault!`);

                toast({
                  title: "✅ Deposit Successful!",
                  description: `Deposited ${amount} USDC and received vault shares.`,
                });

                if (onRefresh) onRefresh();

                setTimeout(() => {
                  setTransactionStage('idle');
                }, 3000);
              }
            }
          } catch (balanceCheckErr) {
            console.warn(`❌ Balance check attempt ${attempts + 1} failed:`, balanceCheckErr);
          }

          attempts++;
        }

        if (!balanceChanged) {
          throw new Error('Transaction submitted but balance not updated yet. Please check back in a moment.');
        }
      } else {
        throw new Error(response.data.message || 'Deposit failed');
      }
    } catch (err: any) {
      console.error('❌ MAVC Yearn Deposit Error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to deposit to MAVC Yearn vault';
      setTransactionError(errorMsg);
      setTransactionStage('error');

      toast({
        title: "❌ Deposit Failed",
        description: errorMsg,
      });

      setTimeout(() => {
        setTransactionStage('idle');
      }, 5000);
    } finally {
      setTransactionLoading(false);
    }
  };

  const handleWithdraw = async (amount: string) => {
    console.log('🚀 MAVC Yearn handleWithdraw called with amount:', amount);

    setShowModal(false);

    try {
      setTransactionLoading(true);
      setTransactionError(null);
      setTransactionSuccess(null);
      setTransactionType('withdraw');
      setTransactionStage('processing');

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

      // Capture initial balance before transaction
      const initialVaultBalance = parseFloat(vaultBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);

      const response = await api.post('/api/v1/mavc-yearn/withdraw', payload);

      if (response.data.status === 'success') {
        console.log('✅ Withdrawal transaction created');
        setTransactionStage('confirming');

        // Poll for balance change
        const maxAttempts = 60;
        let attempts = 0;
        let balanceChanged = false;

        while (attempts < maxAttempts && !balanceChanged) {
          await new Promise(resolve => setTimeout(resolve, 2000));

          const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);

          if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
            // Check if vault balance decreased OR USDC balance increased
            const vaultToken = walletResponse.data.tokenBalances.find((b: any) =>
              b.token && b.token.symbol === 'MAVC_YEARN'
            );

            const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
              b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
            );

            let currentVaultBalance = vaultToken ? parseFloat(vaultToken.amount || "0") : 0;
            let currentUSDCBalance = 0;

            if (allUSDCTokens.length > 0) {
              currentUSDCBalance = allUSDCTokens.reduce((sum: number, token: any) => {
                return sum + parseFloat(token.amount || "0");
              }, 0);
            }

            console.log(`🔍 Attempt ${attempts + 1}: Vault = ${currentVaultBalance}, USDC = ${currentUSDCBalance}`);

            if (currentVaultBalance < initialVaultBalance || currentUSDCBalance > initialUSDCBalance) {
              console.log('✅ Balance changed!');
              balanceChanged = true;
              setTransactionStage('success');

              setVaultBalance(currentVaultBalance.toString());
              setUsdcBalance(currentUSDCBalance.toString());

              setTransactionSuccess(`Successfully withdrew ${amount} vault shares!`);

              toast({
                title: "✅ Withdrawal Successful!",
                description: `Withdrew ${amount} vault shares and received ${(currentUSDCBalance - initialUSDCBalance).toFixed(2)} USDC.`,
              });

              if (onRefresh) onRefresh();

              setTimeout(() => {
                setTransactionStage('idle');
              }, 3000);
            }
          }

          attempts++;
        }

        if (!balanceChanged) {
          throw new Error('Transaction submitted but balance not updated yet. Please check back in a moment.');
        }
      } else {
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('❌ MAVC Yearn Withdraw Error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to withdraw from MAVC Yearn vault';
      setTransactionError(errorMsg);
      setTransactionStage('error');

      toast({
        title: "❌ Withdrawal Failed",
        description: errorMsg,
      });

      setTimeout(() => {
        setTransactionStage('idle');
      }, 5000);
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
    router.push('/customer/grow/hedge-fund-v2/mavc-yearn');
  };

  // Get vault address from Firestore config (TODO: implement config hook)
  const vaultAddress = "0x..."; // Placeholder

  return (
    <>
      <Card
        className="flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl hover:-translate-y-1 bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50 cursor-pointer"
        onClick={handleCardClick}
      >
        <CardHeader className="pb-4">
          <div className="flex justify-between items-start gap-4">
            <div className="flex items-center gap-2">
              <CardTitle className="text-xl text-white">{strategyMetrics.name}</CardTitle>
              <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30 text-xs">
                Yearn v3
              </Badge>
            </div>
            <div className="flex flex-col items-end gap-1">
              <BalanceStatusIndicator
                stage={transactionStage}
                type={transactionType}
                balance={formatTokenBalance(vaultBalance)}
                showShimmer={transactionStage === 'confirming'}
                error={transactionError}
                tokenSymbol="ysMAVC"
              />
              <span className="text-xs text-zinc-500">ysMAVC</span>
            </div>
          </div>
          <CardDescription className="pt-2 text-sm text-zinc-400">{strategyMetrics.description}</CardDescription>
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
                    <span className="font-semibold text-lg text-white">{strategyMetrics.netApy.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-right">
                  <div>
                    <p className="text-xs text-zinc-500">AUM</p>
                    <span className="font-semibold text-lg text-white">
                      ${strategyMetrics.aum.toFixed(2)}{strategyMetrics.aumUnit}
                    </span>
                  </div>
                  <Wallet className="w-6 h-6 text-zinc-500" />
                </div>
              </div>

              <Separator className="bg-zinc-700" />

              <div className="flex justify-between items-center text-center">
                <div className="flex flex-col items-center gap-1">
                  <BarChart className="w-5 h-5 text-blue-400" />
                  <span className="font-semibold text-white">{strategyMetrics.sharpe.toFixed(2)}</span>
                  <span className="text-xs text-zinc-500">Sharpe</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <TrendingDown className="w-5 h-5 text-red-400" />
                  <span className="font-semibold text-white">{strategyMetrics.maxDrawdown.toFixed(2)}%</span>
                  <span className="text-xs text-zinc-500">Max Drawdown</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <Clock className="w-5 h-5 text-zinc-500" />
                  <span className="font-semibold text-white">{strategyMetrics.lockInPeriod}</span>
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
                <span className="font-semibold text-white">{strategyMetrics.participants.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <Percent className="w-5 h-5" />
                <span className="font-semibold text-white">{strategyMetrics.performanceFee.toFixed(1)}%</span>
              </div>
              <Badge className={gradeStyles[strategyMetrics.riskGrade]}>
                Risk: {strategyMetrics.riskGrade}
              </Badge>
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

      <MAVCYearnModal
        visible={showModal}
        onClose={closeModal}
        action={modalAction}
        vaultBalance={vaultBalance}
        usdcBalance={usdcBalance}
        onDeposit={handleDeposit}
        onWithdraw={handleWithdraw}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
        pricePerShare={vaultPricePerShare}
        walletAddress={walletAddress}
        vaultAddress={vaultAddress}
      />
    </>
  );
};

export default MAVCYearnStrategyCard;
