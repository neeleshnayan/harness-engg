"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet, Users, Percent, BarChart, Clock, Shield } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn, formatTokenBalance } from "@/lib/utils";
import MAVCModal from "./MAVCModal";
import api from "@/lib/api";
import { useMAVCConfig } from "@/hooks/useMAVCConfig";
import { useMAVCPrice } from "@/hooks/useMAVCPrice";
import { useSubgraphData } from "@/hooks/useSubgraphData";
import { BalanceStatusIndicator, BalanceTransactionStage, BalanceTransactionType } from "./BalanceStatusIndicator";
import { useToast } from "@/hooks/use-toast";

interface MAVCStrategyCardProps {
  onRefresh?: () => void;
}

const MAVCStrategyCard: React.FC<MAVCStrategyCardProps> = ({ onRefresh }) => {
  const router = useRouter();
  const { data: mavcConfig } = useMAVCConfig();
  const { toast } = useToast();

  // Fetch MAVC price from subgraph (updates every 60 seconds)
  const { data: mavcPriceData, isLoading: priceLoading, error: priceError } = useMAVCPrice(
    mavcConfig?.subgraph_url
  );

  // Fetch subgraph data to get net MAVC supply
  const { data: subgraphData, isLoading: subgraphLoading, error: subgraphError } = useSubgraphData(mavcConfig?.subgraph_url);
  
  // Debug logging
  useEffect(() => {
    console.log('🔍 MAVC Subgraph Debug:', {
      subgraphUrl: mavcConfig?.subgraph_url,
      subgraphLoading,
      subgraphError: subgraphError?.message,
      hasData: !!subgraphData,
      mavcvaultMetric: subgraphData?.mavcvaultMetric,
    });
    if (subgraphData) {
      console.log('✅ MAVC Subgraph Data:', {
        uniqueDepositors: subgraphData.mavcvaultMetric?.uniqueDepositors,
        mintedShares: subgraphData.mavcvaultMetric?.mintedShares,
        burnedShares: subgraphData.mavcvaultMetric?.burnedShares,
        totalDeposits: subgraphData.mavcvaultMetric?.totalDeposits,
      });
    }
    if (subgraphError) {
      console.error('❌ MAVC Subgraph Error:', subgraphError);
    }
  }, [subgraphData, subgraphError, subgraphLoading, mavcConfig?.subgraph_url]);

  const [mavcBalance, setMavcBalance] = useState("0");
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);
  const [transactionStage, setTransactionStage] = useState<BalanceTransactionStage>('idle');
  const [transactionType, setTransactionType] = useState<BalanceTransactionType>('deposit');

  // Calculate net MAVC supply (minted - burned)
  const netMAVCSupply = useMemo(() => {
    if (!subgraphData?.mavcvaultMetric) return 0;
    const minted = Number(subgraphData.mavcvaultMetric.mintedShares ?? '0');
    const burned = Number(subgraphData.mavcvaultMetric.burnedShares ?? '0');
    return minted - burned;
  }, [subgraphData]);

  // Calculate AUM dynamically: total_MAVC_supply * price_of_MAVC_in_USD
  const calculatedAUM = useMemo(() => {
    if (!mavcPriceData?.price || netMAVCSupply === 0) {
      return { value: mavcConfig?.aum ?? 8.9, unit: 'M' }; // Fallback to config value
    }
    const priceInUSD = Number(mavcPriceData.price);
    const aumInUSD = netMAVCSupply * priceInUSD;

    // Display based on magnitude
    if (aumInUSD >= 1_000_000) {
      return { value: aumInUSD / 1_000_000, unit: 'M' }; // Millions
    } else if (aumInUSD >= 1_000) {
      return { value: aumInUSD / 1_000, unit: 'K' }; // Thousands
    } else {
      return { value: aumInUSD, unit: '' }; // Raw value
    }
  }, [netMAVCSupply, mavcPriceData, mavcConfig?.aum]);

  // Get unique depositors from subgraph data
  const uniqueDepositors = subgraphData?.mavcvaultMetric?.uniqueDepositors ?? mavcConfig?.participants ?? 121;

  // Fetch strategy metrics from database via mavcConfig
  const strategyMetrics = {
    name: mavcConfig?.name ?? "Multi Asset Vault",
    description: mavcConfig?.description ?? "Advanced 50/50 USDC/WETH allocation with high-frequency rebalancing.",
    netApy: mavcConfig?.net_apy ?? 135.3,
    aum: calculatedAUM.value,
    aumUnit: calculatedAUM.unit,
    sharpe: mavcConfig?.sharpe_ratio ?? 0.85,
    maxDrawdown: mavcConfig?.max_drawdown ?? 65.50,
    lockInPeriod: mavcConfig?.lock_in_period ?? "14d",
    participants: uniqueDepositors,
    performanceFee: mavcConfig?.performance_fee ?? 30.0,
    riskGrade: mavcConfig?.risk_grade ?? "D"
  };

  const gradeStyles = {
    A: 'bg-green-500/20 text-green-400 border-green-500/20 hover:bg-green-500/30',
    B: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/30',
    C: 'bg-orange-500/20 text-orange-400 border-orange-500/20 hover:bg-orange-500/30',
    D: 'bg-red-500/20 text-red-400 border-red-500/20 hover:bg-red-500/30',
  };

  useEffect(() => {
    if (mavcConfig?.token_address) {
      fetchBalances();
    }
  }, [mavcConfig?.token_address]);

  const fetchBalances = async () => {
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        console.log('🔍 User Data from localStorage:', parsedData);
        console.log('🔍 Wallet Address being used:', parsedData.wallet_address);

        if (parsedData.wallet_address) {
          setWalletAddress(parsedData.wallet_address);
          // Fetch wallet balances (includes both USDC and MAVC tokens)
          try {
            console.log(`🔍 Fetching wallet balances for: ${parsedData.wallet_address}`);
            const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            console.log('✅ Wallet Balance Response:', walletResponse.data);

            // The API returns tokenBalances array
            if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
              console.log('📋 All token symbols in wallet:', walletResponse.data.tokenBalances.map((t: any) => t.token?.symbol));

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

              // Find MAVC token by the token address from Firestore config
              const mavcTokenAddress = mavcConfig?.token_address;

              const mavcToken = mavcTokenAddress
                ? walletResponse.data.tokenBalances.find((b: any) =>
                    b.token &&
                    b.token.symbol === 'MAVC' &&
                    b.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()
                  )
                : null;

              if (mavcToken) {
                console.log('✅ FOUND MAVC Token with correct address!');
                console.log('🔍 MAVC Token Object:', mavcToken);
                console.log('🔍 MAVC Address:', mavcToken.token?.tokenAddress);
                console.log('🔍 MAVC Amount (from API):', mavcToken.amount);
                console.log('🔍 MAVC Decimals:', mavcToken.token?.decimals);

                // MAVC uses 12 decimals (10^12) - convert to human-readable format
                const rawAmount = parseFloat(mavcToken.amount || "0");
                const humanReadable = rawAmount / Math.pow(10, 12);

                setMavcBalance(humanReadable.toString());
                console.log('✅ MAVC Balance converted:', rawAmount, '/ 10^12 =', humanReadable);
              } else {
                setMavcBalance("0");
                console.log('❌ No MAVC token found with correct address:', mavcTokenAddress);
                const allMavcTokens = walletResponse.data.tokenBalances.filter((t: any) => t.token?.symbol === 'MAVC');
                console.log('📋 All MAVC tokens found:', allMavcTokens.map((t: any) => ({
                  address: t.token?.tokenAddress,
                  amount: t.amount
                })));
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
    console.log('🚀 handleDeposit called with amount:', amount);

    // Close modal immediately to show balance animations
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
      const initialMAVCBalance = parseFloat(mavcBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);
      console.log('💰 Initial MAVC Balance:', initialMAVCBalance);
      console.log('💵 Initial USDC Balance:', initialUSDCBalance);

      console.log('🔍 STEP 1: Calling approve endpoint...');
      const approveResponse = await api.post('/api/v1/mavc/approve', payload);

      if (approveResponse.data.status !== 'success') {
        throw new Error('USDC approval failed');
      }

      // Extract the transaction ID from approval response
      const approveTxId = approveResponse.data.transaction_id;
      console.log('✅ Approval transaction submitted:', approveTxId);
      console.log('🔗 Monitor at: https://console.circle.com/wallets/dev/transactions/' + approveTxId);

      setTransactionStage('approved');
      await new Promise(resolve => setTimeout(resolve, 500)); // Brief pause to show approved state

      // The backend will now poll for approval confirmation before proceeding with deposit
      console.log('🔍 STEP 2: Calling deposit endpoint (will wait for approval confirmation)...');
      setTransactionStage('processing');

      const depositPayload = {
        ...payload,
        approve_tx_id: approveTxId  // Required: backend will wait for this to be confirmed
      };

      const response = await api.post('/api/v1/mavc/deposit', depositPayload);

      if (response.data.status === 'success') {
        console.log('✅ Deposit transaction created');
        console.log('⏳ Waiting for balance to change...');
        setTransactionStage('confirming');

        // Poll for balance change
        const maxAttempts = 60; // 60 attempts = 2 minutes max
        let attempts = 0;
        let balanceChanged = false;

        while (attempts < maxAttempts && !balanceChanged) {
          await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds between checks

          // Fetch updated balance
          const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);

          if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
            // Check MAVC balance
            const mavcTokenAddress = mavcConfig?.token_address;
            const mavcToken = mavcTokenAddress
              ? walletResponse.data.tokenBalances.find((b: any) =>
                  b.token &&
                  b.token.symbol === 'MAVC' &&
                  b.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()
                )
              : null;

            if (mavcToken) {
              const rawAmount = parseFloat(mavcToken.amount || "0");
              const currentMAVCBalance = rawAmount / Math.pow(10, 12);
              console.log(`🔍 Attempt ${attempts + 1}: MAVC Balance = ${currentMAVCBalance} (initial: ${initialMAVCBalance})`);

              // Check if MAVC balance increased
              if (currentMAVCBalance > initialMAVCBalance) {
                console.log('✅ Balance changed! MAVC increased from', initialMAVCBalance, 'to', currentMAVCBalance);
                balanceChanged = true;
                setTransactionStage('success');

                // Update local state
                setMavcBalance(currentMAVCBalance.toString());

                // Also update USDC balance
                const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
                  b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
                );
                if (allUSDCTokens.length > 0) {
                  const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                    return sum + parseFloat(token.amount || "0");
                  }, 0);
                  setUsdcBalance(totalUSDC.toString());
                }

                const successMessage = `Successfully deposited ${amount} USDC to MAVC!`;
                setTransactionSuccess(successMessage);

                // Show success toast notification
                toast({
                  title: "✅ Deposit Successful!",
                  description: `Deposited ${amount} USDC and received ${currentMAVCBalance.toFixed(6)} MAVC tokens.`,
                });

                if (onRefresh) onRefresh();

                // Reset to idle after showing success
                setTimeout(() => {
                  setTransactionStage('idle');
                }, 3000);
              }
            }
          }

          attempts++;
        }

        if (!balanceChanged) {
          console.warn('⚠️ Balance did not change within timeout period');
          throw new Error('Transaction submitted but balance not updated yet. Please check back in a moment.');
        }
      } else {
        throw new Error(response.data.message || 'Deposit failed');
      }
    } catch (err: any) {
      console.error('❌ MAVC Deposit Error:', err);
      const errorMsg = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to deposit to MAVC vault';
      setTransactionError(errorMsg);
      setTransactionStage('error');

      // Show error toast notification
      toast({
        title: "❌ Deposit Failed",
        description: errorMsg,
      });

      // Reset to idle after showing error
      setTimeout(() => {
        setTransactionStage('idle');
      }, 5000);
    } finally {
      console.log('🏁 Finally block: Setting transactionLoading to false');
      setTransactionLoading(false);
    }
  };

  // MAVC Price in USDC (fetched from subgraph, updates every 60 seconds)
  const mavcPriceInUSDC = mavcPriceData?.price
    ? formatTokenBalance(mavcPriceData.price)
    : null;

  const handleWithdraw = async (amount: string) => {
    console.log('🚀 handleWithdraw called with amount:', amount);

    // Close modal immediately to show balance animations
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
      const initialMAVCBalance = parseFloat(mavcBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);
      console.log('💰 Initial MAVC Balance:', initialMAVCBalance);
      console.log('💵 Initial USDC Balance:', initialUSDCBalance);

      const response = await api.post('/api/v1/mavc/withdraw', payload);

      if (response.data.status === 'success') {
        console.log('✅ Withdrawal transaction created');
        console.log('⏳ Waiting for balance to change...');
        setTransactionStage('confirming');

        // Poll for balance change
        const maxAttempts = 60; // 60 attempts = 2 minutes max
        let attempts = 0;
        let balanceChanged = false;

        while (attempts < maxAttempts && !balanceChanged) {
          await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds between checks

          // Fetch updated balance
          const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);

          if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
            // Check MAVC balance (should decrease) and USDC balance (should increase)
            const mavcTokenAddress = mavcConfig?.token_address;
            const mavcToken = mavcTokenAddress
              ? walletResponse.data.tokenBalances.find((b: any) =>
                  b.token &&
                  b.token.symbol === 'MAVC' &&
                  b.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()
                )
              : null;

            // Check USDC balance
            const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
              b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
            );

            let currentMAVCBalance = 0;
            let currentUSDCBalance = 0;

            if (mavcToken) {
              const rawAmount = parseFloat(mavcToken.amount || "0");
              currentMAVCBalance = rawAmount / Math.pow(10, 12);
            }

            if (allUSDCTokens.length > 0) {
              currentUSDCBalance = allUSDCTokens.reduce((sum: number, token: any) => {
                return sum + parseFloat(token.amount || "0");
              }, 0);
            }

            console.log(`🔍 Attempt ${attempts + 1}: MAVC = ${currentMAVCBalance} (initial: ${initialMAVCBalance}), USDC = ${currentUSDCBalance} (initial: ${initialUSDCBalance})`);

            // Check if MAVC balance decreased OR USDC balance increased
            if (currentMAVCBalance < initialMAVCBalance || currentUSDCBalance > initialUSDCBalance) {
              console.log('✅ Balance changed! MAVC:', initialMAVCBalance, '->', currentMAVCBalance, '| USDC:', initialUSDCBalance, '->', currentUSDCBalance);
              balanceChanged = true;
              setTransactionStage('success');

              // Update local state
              setMavcBalance(currentMAVCBalance.toString());
              setUsdcBalance(currentUSDCBalance.toString());

              const successMessage = `Successfully withdrew ${amount} MAVC tokens!`;
              setTransactionSuccess(successMessage);

              // Show success toast notification
              toast({
                title: "✅ Withdrawal Successful!",
                description: `Withdrew ${amount} MAVC tokens and received ${(currentUSDCBalance - initialUSDCBalance).toFixed(2)} USDC.`,
              });

              if (onRefresh) onRefresh();

              // Reset to idle after showing success
              setTimeout(() => {
                setTransactionStage('idle');
              }, 3000);
            }
          }

          attempts++;
        }

        if (!balanceChanged) {
          console.warn('⚠️ Balance did not change within timeout period');
          throw new Error('Transaction submitted but balance not updated yet. Please check back in a moment.');
        }
      } else {
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('❌ MAVC Withdraw Error:', err);
      const errorMsg = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to withdraw from MAVC vault';
      setTransactionError(errorMsg);
      setTransactionStage('error');

      // Show error toast notification
      toast({
        title: "❌ Withdrawal Failed",
        description: errorMsg,
      });

      // Reset to idle after showing error
      setTimeout(() => {
        setTransactionStage('idle');
      }, 5000);
    } finally {
      console.log('🏁 Finally block: Setting transactionLoading to false');
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


  return (
    <>
      <Card 
        className="flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl hover:-translate-y-1 bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50 cursor-pointer"
        onClick={handleCardClick}
      >
        <CardHeader className="pb-4">
          <div className="flex justify-between items-start gap-4">
            <CardTitle className="text-xl text-white">{strategyMetrics.name}</CardTitle>
            <div className="flex flex-col items-end gap-1">
              <BalanceStatusIndicator
                stage={transactionStage}
                type={transactionType}
                balance={formatTokenBalance(mavcBalance)}
                showShimmer={transactionStage === 'confirming'}
                error={transactionError}
              />
              {priceLoading ? (
                <span className="text-xs text-zinc-500">Loading price...</span>
              ) : priceError ? (
                <span className="text-xs text-red-400">Price unavailable</span>
              ) : mavcPriceInUSDC ? (
                <span className="text-xs text-green-400 font-medium whitespace-nowrap">
                  1 MAVC = ${mavcPriceInUSDC}
                </span>
              ) : null}
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
        mavcPrice={mavcPriceInUSDC}
        walletAddress={walletAddress}
        tokenAddress="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
      />
    </>
  );
};

export default MAVCStrategyCard;

