"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet, Users, Percent, BarChart, Clock } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { formatTokenBalance } from "@/lib/utils";
import MAVCModal from "./MAVCModal";
import api from "@/lib/api";
import { useMAVPConfig } from "@/hooks/useMAVPConfig";
import { useMAVPPrice } from "@/hooks/useMAVPPrice";
import { useMAVPSubgraphData } from "@/hooks/useMAVPSubgraphData";
import { BalanceStatusIndicator, BalanceTransactionStage, BalanceTransactionType } from "./BalanceStatusIndicator";
import { useToast } from "@/hooks/use-toast";

interface MAVPStrategyCardProps {
  onRefresh?: () => void;
}

const MAVPStrategyCard: React.FC<MAVPStrategyCardProps> = ({ onRefresh }) => {
  const router = useRouter();
  const { data: mavpConfig } = useMAVPConfig();
  const { toast } = useToast();

  // Fetch MAVP price from subgraph (updates every 60 seconds)
  const { data: mavpPriceData, isLoading: priceLoading, error: priceError } = useMAVPPrice(
    mavpConfig?.subgraph_url
  );

  // Fetch subgraph data to get net MAVP supply
  const { data: subgraphData } = useMAVPSubgraphData(mavpConfig?.subgraph_url);

  const [mavpBalance, setMavpBalance] = useState("0");
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);
  const [transactionStage, setTransactionStage] = useState<BalanceTransactionStage>('idle');
  const [transactionType, setTransactionType] = useState<BalanceTransactionType>('deposit');

  // Calculate net MAVP supply (minted - burned)
  const netMAVPSupply = useMemo(() => {
    if (!subgraphData?.mavpvaultMetric) return 0;
    const minted = Number(subgraphData.mavpvaultMetric.mintedShares ?? '0');
    const burned = Number(subgraphData.mavpvaultMetric.burnedShares ?? '0');
    return minted - burned;
  }, [subgraphData]);

  // Calculate AUM dynamically: total_MAVP_supply * price_of_MAVP_in_USD
  const calculatedAUM = useMemo(() => {
    if (!mavpPriceData?.price || netMAVPSupply === 0) {
      return { value: mavpConfig?.aum ?? 15.2, unit: 'M' }; // Fallback to config value
    }
    const priceInUSD = Number(mavpPriceData.price);
    const aumInUSD = netMAVPSupply * priceInUSD;

    // Display based on magnitude
    if (aumInUSD >= 1_000_000) {
      return { value: aumInUSD / 1_000_000, unit: 'M' }; // Millions
    } else if (aumInUSD >= 1_000) {
      return { value: aumInUSD / 1_000, unit: 'K' }; // Thousands
    } else {
      return { value: aumInUSD, unit: '' }; // Raw value
    }
  }, [netMAVPSupply, mavpPriceData, mavpConfig?.aum]);

  // Get unique depositors from subgraph data
  const uniqueDepositors = subgraphData?.mavpvaultMetric?.uniqueDepositors ?? mavpConfig?.participants ?? 342;

  // MAVP Price in USDC (fetched from subgraph, updates every 60 seconds)
  const mavpPriceInUSDC = mavpPriceData?.price
    ? formatTokenBalance(mavpPriceData.price)
    : null;

  // Fetch strategy metrics from database via mavpConfig
  const strategyMetrics = {
    name: mavpConfig?.name ?? "Multi Asset Vault Protocol",
    description: mavpConfig?.description ?? "Advanced yield farming protocol with automated rebalancing and risk management.",
    netApy: mavpConfig?.net_apy ?? 89.7,
    aum: calculatedAUM.value,
    aumUnit: calculatedAUM.unit,
    sharpe: mavpConfig?.sharpe_ratio ?? 1.45,
    maxDrawdown: mavpConfig?.max_drawdown ?? 28.3,
    lockInPeriod: mavpConfig?.lock_in_period ?? "7d",
    participants: uniqueDepositors,
    performanceFee: mavpConfig?.performance_fee ?? 15.0,
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
          setWalletAddress(parsedData.wallet_address);

          try {
            const mavpResponse = await api.get(`/api/v1/mavp/balance/${parsedData.wallet_address}`);
            setMavpBalance(mavpResponse.data.balance || "0");
          } catch (err) {
            console.warn('MAVP balance not available:', err);
            setMavpBalance("0");
          }

          try {
            const usdcResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            if (usdcResponse.data && Array.isArray(usdcResponse.data.tokenBalances)) {
              const allUSDCTokens = usdcResponse.data.tokenBalances.filter((b: any) =>
                b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
              );
              if (allUSDCTokens.length > 0) {
                const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                  return sum + parseFloat(token.amount || "0");
                }, 0);
                setUsdcBalance(totalUSDC.toString());
              } else {
                setUsdcBalance("0");
              }
            } else {
              setUsdcBalance("0");
            }
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
      const initialMAVPBalance = parseFloat(mavpBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);
      console.log('💰 Initial MAVP Balance:', initialMAVPBalance);
      console.log('💵 Initial USDC Balance:', initialUSDCBalance);

      console.log('🔍 STEP 1: Calling approve endpoint...');
      const approveResponse = await api.post('/api/v1/mavp/approve', payload);

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

      const response = await api.post('/api/v1/mavp/deposit', depositPayload);

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
          try {
            const mavpResponse = await api.get(`/api/v1/mavp/balance/${parsedData.wallet_address}`);
            const currentMAVPBalance = parseFloat(mavpResponse.data.balance || "0");
            
            console.log(`🔍 Attempt ${attempts + 1}: MAVP Balance = ${currentMAVPBalance} (initial: ${initialMAVPBalance})`);

            // Check if MAVP balance increased
            if (currentMAVPBalance > initialMAVPBalance) {
              console.log('✅ Balance changed! MAVP increased from', initialMAVPBalance, 'to', currentMAVPBalance);
              balanceChanged = true;
              setTransactionStage('success');

              // Update local state
              setMavpBalance(currentMAVPBalance.toString());

              // Also update USDC balance
              const usdcResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
              if (usdcResponse.data && Array.isArray(usdcResponse.data.tokenBalances)) {
                const allUSDCTokens = usdcResponse.data.tokenBalances.filter((b: any) =>
                  b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
                );
                if (allUSDCTokens.length > 0) {
                  const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                    return sum + parseFloat(token.amount || "0");
                  }, 0);
                  setUsdcBalance(totalUSDC.toString());
                }
              }

              const successMessage = `Successfully deposited ${amount} USDC to MAVP!`;
              setTransactionSuccess(successMessage);

              // Show success toast notification
              toast({
                title: "✅ Deposit Successful!",
                description: `Deposited ${amount} USDC and received ${currentMAVPBalance.toFixed(6)} MAVP tokens.`,
              });

              if (onRefresh) onRefresh();

              // Reset to idle after showing success
              setTimeout(() => {
                setTransactionStage('idle');
              }, 3000);
            }
          } catch (balanceErr) {
            console.warn('Error fetching balance during polling:', balanceErr);
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
      console.error('❌ MAVP Deposit Error:', err);
      const errorMsg = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to deposit to MAVP vault';
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
      const initialMAVPBalance = parseFloat(mavpBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);
      console.log('💰 Initial MAVP Balance:', initialMAVPBalance);
      console.log('💵 Initial USDC Balance:', initialUSDCBalance);

      const response = await api.post('/api/v1/mavp/withdraw', payload);

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

          // Fetch updated balances
          try {
            const mavpResponse = await api.get(`/api/v1/mavp/balance/${parsedData.wallet_address}`);
            const currentMAVPBalance = parseFloat(mavpResponse.data.balance || "0") / 1e18;

            const usdcResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            let currentUSDCBalance = 0;

            if (usdcResponse.data && Array.isArray(usdcResponse.data.tokenBalances)) {
              const allUSDCTokens = usdcResponse.data.tokenBalances.filter((b: any) =>
                b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
              );
              if (allUSDCTokens.length > 0) {
                currentUSDCBalance = allUSDCTokens.reduce((sum: number, token: any) => {
                  return sum + parseFloat(token.amount || "0");
                }, 0);
              }
            }

            console.log(`🔍 Attempt ${attempts + 1}: MAVP = ${currentMAVPBalance} (initial: ${initialMAVPBalance}), USDC = ${currentUSDCBalance} (initial: ${initialUSDCBalance})`);

            // Check if MAVP balance decreased OR USDC balance increased
            if (currentMAVPBalance < initialMAVPBalance || currentUSDCBalance > initialUSDCBalance) {
              console.log('✅ Balance changed! MAVP:', initialMAVPBalance, '->', currentMAVPBalance, '| USDC:', initialUSDCBalance, '->', currentUSDCBalance);
              balanceChanged = true;
              setTransactionStage('success');

              // Update local state
              setMavpBalance(currentMAVPBalance.toString());
              setUsdcBalance(currentUSDCBalance.toString());

              const successMessage = `Successfully withdrew ${amount} MAVP tokens!`;
              setTransactionSuccess(successMessage);

              // Show success toast notification
              toast({
                title: "✅ Withdrawal Successful!",
                description: `Withdrew ${amount} MAVP tokens and received ${(currentUSDCBalance - initialUSDCBalance).toFixed(2)} USDC.`,
              });

              if (onRefresh) onRefresh();

              // Reset to idle after showing success
              setTimeout(() => {
                setTransactionStage('idle');
              }, 3000);
            }
          } catch (balanceErr) {
            console.warn('Error fetching balance during polling:', balanceErr);
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
      console.error('❌ MAVP Withdraw Error:', err);
      const errorMsg = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to withdraw from MAVP vault';
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
    router.push('/customer/grow/hedge-fund-v2/mavp');
  };

  const formatBalance = (balance: string): string => {
    try {
      const numBalance = parseFloat(balance) / 1e18;
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
            <CardTitle className="text-xl text-white">{strategyMetrics.name}</CardTitle>
            <div className="flex flex-col items-end gap-1">
              <BalanceStatusIndicator
                stage={transactionStage}
                type={transactionType}
                balance={formatBalance(mavpBalance)}
                tokenSymbol="MAVP"
              />
              {priceLoading ? (
                <span className="text-xs text-zinc-500">Loading price...</span>
              ) : priceError ? (
                <span className="text-xs text-red-400">Price unavailable</span>
              ) : mavpPriceInUSDC ? (
                <span className="text-xs text-green-400 font-medium">
                  1 MAVP = ${mavpPriceInUSDC}
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
        mavcBalance={mavpBalance}
        usdcBalance={usdcBalance}
        onDeposit={handleDeposit}
        onWithdraw={handleWithdraw}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
        mavcPrice={mavpPriceInUSDC}
        walletAddress={walletAddress}
        tokenAddress="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
        tokenSymbol="MAVP"
      />
    </>
  );
};

export default MAVPStrategyCard;

