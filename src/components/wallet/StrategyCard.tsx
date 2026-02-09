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
import { hedgeFundApi } from "@/lib/api";
import { StrategyName, useStrategyConfig } from "@/hooks/useStrategyConfig";
import { useStrategyPrice } from "@/hooks/useStrategyPrice";
import { useStrategySubgraphData } from "@/hooks/useStrategySubgraphData";
import { useYearnAUM } from "@/hooks/useYearnAUM";
import { BalanceStatusIndicator, BalanceTransactionStage, BalanceTransactionType } from "./BalanceStatusIndicator";
import StrategyModal from "./StrategyModal";

interface StrategyCardProps {
  strategyName: string; // Changed from StrategyName to string for dynamic support
  onRefresh?: () => void;
  onCardClick?: () => void;
  usdcBalance?: string;
  strategyBalance?: string; // Pre-fetched strategy balance from parent
  strategyBalanceWei?: string; // Pre-fetched raw wei balance from parent
  strategyData?: any; // Dynamic config
}

// Strategy-specific configuration (Legacy support)
const STRATEGY_DETAILS__LEGACY: Record<string, {
  tokenSymbol: string;
  routePath: string;
  metricField: 'strategyMetric';
  useTokenDetection?: boolean;
}> = {
  YEARN_WETH: {
    tokenSymbol: 'ysWETH',
    routePath: '/customer/grow/hedge-fund-v2/yearn-weth',
    metricField: 'strategyMetric',
    useTokenDetection: false,
  },
};

const StrategyCard: React.FC<StrategyCardProps> = ({ strategyName, onRefresh, onCardClick, usdcBalance, strategyBalance: strategyBalanceProp, strategyBalanceWei: strategyBalanceWeiProp, strategyData }) => {
  const router = useRouter();
  const { toast } = useToast();

  const safeStrategyName = strategyName || "";

  // Dynamic Details
  const strategyDetails = STRATEGY_DETAILS__LEGACY[safeStrategyName] || {
    tokenSymbol: strategyData?.symbol || 'TOKEN',
    routePath: `/customer/grow/hedge-fund-v2/${safeStrategyName.toLowerCase()}`,
    metricField: 'strategyMetric', // Generic metric field
    useTokenDetection: false,
  };

  const { data: config_fetched, isLoading: configLoading_fetched } = useStrategyConfig(strategyName as StrategyName);

  // Use passed Data if available, else use fetched config
  const config = strategyData || config_fetched;
  const configLoading = strategyData ? false : configLoading_fetched;

  const { data: priceData, isLoading: priceLoading, error: priceError } = useStrategyPrice(
    strategyName,
    config?.subgraph_url
  );
  const { data: subgraphData, isLoading: subgraphLoading } = useStrategySubgraphData(strategyName, config?.subgraph_url);
  const { data: yearnAUM } = useYearnAUM(strategyName);

  const [strategyBalance, setStrategyBalance] = useState("0");
  const [strategyBalanceWei, setStrategyBalanceWei] = useState("0");
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [usdcBalanceState, setUsdcBalance] = useState("0"); // Renamed to differentiate from prop
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);
  const [transactionStage, setTransactionStage] = useState<BalanceTransactionStage>('idle');
  const [transactionType, setTransactionType] = useState<BalanceTransactionType>('deposit');

  // Yearn-specific state
  const [vaultPricePerShare, setVaultPricePerShare] = useState(1.0);

  // Calculate net supply from subgraph
  const netSupply = useMemo(() => {
    const metric = subgraphData?.strategyMetric;
    if (!metric) return 0;
    const minted = Number(metric.mintedShares ?? '0');
    const burned = Number(metric.burnedShares ?? '0');
    return minted - burned;
  }, [subgraphData]);

  // Calculate AUM dynamically
  const calculatedAUM = useMemo(() => {


    if (!priceData?.price || netSupply === 0) {
      return { value: config?.aum ?? 8.9, unit: '' };
    }
    const priceInUSD = Number(priceData.price);
    const aumInUSD = netSupply * priceInUSD;

    if (aumInUSD >= 1_000_000) {
      return { value: aumInUSD / 1_000_000, unit: 'M' };
    } else if (aumInUSD >= 1_000) {
      return { value: aumInUSD / 1_000, unit: 'K' };
    } else {
      return { value: aumInUSD, unit: '' };
    }
  }, [strategyName, yearnAUM, netSupply, priceData, config?.aum]);

  const uniqueDepositors = subgraphData?.strategyMetric?.uniqueDepositors ?? config?.participants ?? 121;

  // Strategy metrics from config
  const strategyMetrics = {
    name: config?.name || safeStrategyName || 'Strategy',
    description: config?.description ?? '',
    netApy: config?.net_apy ?? 0,
    aum: calculatedAUM.value,
    aumUnit: calculatedAUM.unit,
    sharpe: config?.sharpe_ratio ?? 0,
    maxDrawdown: config?.max_drawdown ?? 0,
    lockInPeriod: config?.lock_in_period ?? 'None',
    participants: uniqueDepositors,
    performanceFee: config?.performance_fee ?? 0,
    riskGrade: config?.risk_grade ?? 'B'
  };

  const gradeStyles = {
    A: 'bg-green-500/20 text-green-400 border-green-500/20 hover:bg-green-500/30',
    B: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/30',
    C: 'bg-orange-500/20 text-orange-400 border-orange-500/20 hover:bg-orange-500/30',
    D: 'bg-red-500/20 text-red-400 border-red-500/20 hover:bg-red-500/30',
  };

  // OPTIMIZED: Initialize wallet address only - balances come from props
  const fetchBalances = async () => {
    setBalanceLoading(true);
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        if (parsedData.wallet_address) {
          setWalletAddress(parsedData.wallet_address);

          // Use pre-fetched balances from parent component (batch API call)
          if (typeof usdcBalance !== 'undefined') {
            setUsdcBalance(usdcBalance);
          }


          if (typeof strategyBalanceProp !== 'undefined') {
            setStrategyBalance(strategyBalanceProp);
          }

          if (typeof strategyBalanceWeiProp !== 'undefined') {
            setStrategyBalanceWei(strategyBalanceWeiProp);
          }

          console.log(`✅ [OPTIMIZED] ${strategyName} - Using pre-fetched balance: ${strategyBalanceProp} (${strategyBalanceWeiProp} wei)`);
        }
      }
    } catch (err: any) {
      console.error(`❌ Error initializing ${strategyName}:`, err);
    } finally {
      setBalanceLoading(false);
    }
  };

  useEffect(() => {
    if (config) {
      fetchBalances();
    }
  }, [config]);

  // Update USDC balance if prop changes
  useEffect(() => {
    if (typeof usdcBalance !== 'undefined') {
      setUsdcBalance(usdcBalance);
    }
  }, [usdcBalance]);

  // Update strategy balance if prop changes
  useEffect(() => {
    if (typeof strategyBalanceProp !== 'undefined') {
      setStrategyBalance(strategyBalanceProp);
    }
    if (typeof strategyBalanceWeiProp !== 'undefined') {
      setStrategyBalanceWei(strategyBalanceWeiProp);
    }
  }, [strategyBalanceProp, strategyBalanceWeiProp]);

  // Calculate price in USDC (only for MAVC and MAVP, not Yearn)
  const priceInUSDC = useMemo(() => {
    if (!priceData?.price) return null;
    return Number(priceData.price).toFixed(2);
  }, [priceData]);

  // Handle deposit
  const handleDeposit = async (amount: string) => {
    setShowModal(false);
    try {
      setTransactionLoading(true);
      setTransactionError(null);
      setTransactionSuccess(null);
      setTransactionType('deposit');
      setTransactionStage('approving');

      const userData = localStorage.getItem('userData');
      if (!userData) throw new Error('User data not found');

      const parsedData = JSON.parse(userData);
      if (!parsedData.wallet_address) throw new Error('Wallet address not found');

      // Convert human-readable amount to wei
      const amountFloat = parseFloat(amount);
      const decimals = config?.asset_decimals || 6;
      const amountWei = Math.floor(amountFloat * Math.pow(10, decimals)).toString();

      // Step 1: Approve
      const approveResponse = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/approve`, {
        amount: amountWei,  // Send wei amount
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
      });

      if (!approveResponse.data.transaction_id && !approveResponse.data.approve_tx) {
        throw new Error('Approval transaction ID not returned');
      }

      const approveTxId = approveResponse.data.transaction_id || approveResponse.data.approve_tx;
      setTransactionStage('confirming');

      // Step 2: Wait for approval and deposit
      await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds for approval

      const depositResponse = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/deposit`, {
        amount: amountWei,  // Send wei amount
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
        approve_tx_id: approveTxId,
      });

      if (depositResponse.data.status === 'success') {
        // Poll blockchain directly for balance update
        const initialBalance = parseFloat(strategyBalance);
        let attempts = 0;
        const maxAttempts = 30; // Poll for up to 60 seconds

        const pollBalance = async () => {
          attempts++;

          try {
            // Fetch fresh balance directly from blockchain via backend API
            const balanceResponse = await hedgeFundApi.get(`/api/v1/strategy/${strategyName}/balance/${parsedData.wallet_address}`);

            if (balanceResponse.data) {
              const balance_wei = balanceResponse.data.balance || "0";
              const contract_decimals = balanceResponse.data.decimals || 18;

              let display_decimals = contract_decimals;

              const currentBalance = parseFloat(balance_wei) / Math.pow(10, display_decimals);

              // Check if balance increased (deposit should increase balance)
              if (currentBalance > initialBalance || attempts >= maxAttempts) {
                // Balance updated or timeout reached
                setStrategyBalance(currentBalance.toString());
                setStrategyBalanceWei(balance_wei); // Update wei balance too
                setTransactionStage('success');
                if (onRefresh) onRefresh();
                return;
              }
            }
          } catch (error) {
            // Silently handle balance poll error
          }

          // Keep polling
          setTimeout(pollBalance, 2000);
        };

        // Start polling immediately
        setTimeout(pollBalance, 2000);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || `Failed to deposit to ${strategyName}`;
      setTransactionError(errorMsg);
      setTransactionStage('error');
      toast({
        title: "❌ Deposit Failed",
        description: errorMsg,
      });
    } finally {
      setTransactionLoading(false);
    }
  };

  // Handle withdraw
  const handleWithdraw = async (amount: string) => {
    setShowModal(false);
    try {
      setTransactionLoading(true);
      setTransactionError(null);
      setTransactionSuccess(null);
      setTransactionType('withdraw');
      setTransactionStage('confirming');

      const userData = localStorage.getItem('userData');
      if (!userData) throw new Error('User data not found');

      const parsedData = JSON.parse(userData);
      if (!parsedData.wallet_address) throw new Error('Wallet address not found');

      // For MAVC_YEARN: send raw decimal string (e.g., "10")
      // For other strategies: convert to wei format
      
      // LOGIC FIX: Check if we are withdrawing MAX (amount matches display balance)
      // If so, use the exact wei balance to avoid precision errors
      let amountToSend = "0";

      // If user input matches the displayed balance string exactly OR matches the formatted wei balance
      if (amount === strategyBalance && strategyBalanceWei && strategyBalanceWei !== "0") {
          console.log(`✅ [PRECISION] Using exact wei balance for withdrawal: ${strategyBalanceWei}`);
          amountToSend = strategyBalanceWei;
      } else {
          // Fallback to calculation
          const amountFloat = parseFloat(amount);
          
          // CRITICAL FIX: If asset_decimals is 6 (USDC), share_decimals MUST be 6.
          // Existing configs might have erroneously saved share_decimals=18 in the DB, so we must override it.
          let decimals = 18;
          if (config?.asset_decimals === 6) {
              decimals = 6;
          } else {
              decimals = config?.share_decimals || config?.asset_decimals || 18;
          }
          
          console.log(`[DECIMALS] Strategy: ${strategyName}, AssetDecimals: ${config?.asset_decimals}, ShareDecimals: ${config?.share_decimals}, USED: ${decimals}`);
          
          // Check if calculate wei > strategyBalanceWei (if available)
          // Use BigInt for precision check if possible, or just be careful. 
          // Since we don't have BigInt easy access here without potentially messing up older browsers/types (though typical modern React is fine), 
          // we'll stick to string logic or use the float calc but cap it if it's close.
          
          const calculatedWeiCtx = Math.floor(amountFloat * Math.pow(10, decimals)).toString();
          
          // If we have wei balance, and calculated is > wei balance, CAP IT.
          if (strategyBalanceWei && strategyBalanceWei !== "0") {
             // Simple string comparison for large numbers is tricky, convert to BigInt
             try {
                 const calcBI = BigInt(calculatedWeiCtx);
                 const balanceBI = BigInt(strategyBalanceWei);
                 
                 if (calcBI >= balanceBI) {
                      // SANITY CHECK: Only cap if the input amount is actually close to the Max Balance.
                      // This prevents decimal mismatches (e.g. 18 dec vs 6 dec) from triggering a full withdrawal
                      // when the user only wanted a small amount.
                      const maxBalFloat = parseFloat(strategyBalance);
                      
                      // If user is requesting less than 95% of balance, but Wei calc is >= Balance Wei,
                      // it's a configuration error (decimals), NOT a precision error.
                      // Do NOT cap. Let it fail on-chain (or send huge amount) rather than force-withdrawing everything.
                      if (amountFloat < maxBalFloat * 0.95) {
                          console.warn(`⚠️ [DECIMAL MISMATCH] Input ${amountFloat} << Balance ${maxBalFloat} but Wei ${calcBI} >= ${balanceBI}. Using calculated.`);
                          amountToSend = calculatedWeiCtx;
                      } else {
                          console.log(`⚠️ [PRECISION] Capping withdrawal at max balance: ${strategyBalanceWei}`);
                          amountToSend = strategyBalanceWei;
                      }
                 } else {
                      amountToSend = calculatedWeiCtx;
                 }
             } catch (e) {
                 amountToSend = calculatedWeiCtx;
             }
          } else {
             amountToSend = calculatedWeiCtx;
          }
      }

      const response = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/withdraw`, {
        amount: amountToSend,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
      });

      if (response.data.status === 'success') {
        // Poll blockchain directly for balance update
        const initialBalance = parseFloat(strategyBalance);
        let attempts = 0;
        const maxAttempts = 30; // Poll for up to 60 seconds

        const pollBalance = async () => {
          attempts++;

          try {
            // Fetch fresh balance directly from blockchain via backend API
            const balanceResponse = await hedgeFundApi.get(`/api/v1/strategy/${strategyName}/balance/${parsedData.wallet_address}`);

            if (balanceResponse.data) {
              const balance_wei = balanceResponse.data.balance || "0";
              const contract_decimals = balanceResponse.data.decimals || 18;

              let display_decimals = contract_decimals;

              const currentBalance = parseFloat(balance_wei) / Math.pow(10, display_decimals);

              // Check if balance decreased (withdraw should decrease balance)
              if (currentBalance < initialBalance || attempts >= maxAttempts) {
                  setStrategyBalance(currentBalance.toString());
                  setStrategyBalanceWei(balance_wei); // Update Wei balance
                  setTransactionStage('success');
                  if (onRefresh) onRefresh();
                  return;
              }
            }
          } catch (error) {
            // Silently handle balance poll error
          }

          // Keep polling
          setTimeout(pollBalance, 2000);
        };

        // Start polling immediately
        setTimeout(pollBalance, 2000);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || `Failed to withdraw from ${strategyName}`;
      setTransactionError(errorMsg);
      setTransactionStage('error');
      toast({
        title: "❌ Withdrawal Failed",
        description: errorMsg,
      });
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
    if (parseFloat(strategyBalance) === 0) return;
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
    if (onCardClick) {
      onCardClick();
    } else {
      router.push(strategyDetails.routePath);
    }
  };

  return (
    <>
      <Card
        className="bg-transparent bg-no-repeat bg-cover bg-center backdrop-blur-3xl rounded-3xl p-0 shadow-2xl border border-white/10 mb-8 transition-all duration-300 overflow-hidden"
        style={{ backgroundImage: "url('/wallet-bg.svg')" }}
        onClick={handleCardClick}
      >
        <CardHeader className="relative pb-3 sm:pb-4">
          <div className="flex flex-col sm:flex-row justify-between items-start gap-3 sm:gap-4">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg sm:text-xl text-white">{strategyMetrics.name}</CardTitle>
            </div>
            <div className="flex flex-col items-start sm:items-end gap-1 w-full sm:w-auto">
              {balanceLoading || configLoading ? (
                <div className="flex items-center gap-2 px-3 py-1 rounded-lg border bg-zinc-700/20 border-zinc-700/30">
                  <div className="animate-spin rounded-full h-3 w-3 border-2 border-zinc-400 border-t-transparent"></div>
                  <span className="text-sm font-semibold text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-white to-purple-300 animate-shimmer whitespace-nowrap">
                    ••• {strategyDetails.tokenSymbol}
                  </span>
                </div>
              ) : (
                <BalanceStatusIndicator
                  stage={transactionStage}
                  type={transactionType}
                  balance={formatTokenBalance(strategyBalance)}
                  showShimmer={transactionStage === 'confirming'}
                  error={transactionError}
                  tokenSymbol={strategyDetails.tokenSymbol}
                />
              )}
              {priceLoading || configLoading ? (
                <span className="text-xs text-zinc-500 animate-pulse">Loading price...</span>
              ) : priceError ? (
                <span className="text-xs text-red-400">Price unavailable</span>
              ) : priceInUSDC ? (
                <span className="text-xs text-green-400 font-medium whitespace-nowrap">
                  1 {strategyDetails.tokenSymbol} = ${priceInUSDC}
                </span>
              ) : null}
            </div>
          </div>
          <CardDescription className="pt-2 text-xs sm:text-sm text-zinc-400 line-clamp-2">{strategyMetrics.description}</CardDescription>
        </CardHeader>

        <CardContent className="relative flex-grow space-y-4 sm:space-y-5">
          <div className="space-y-3 sm:space-y-4">
            <h4 className="text-xs sm:text-sm text-zinc-400 font-semibold tracking-wide">Key Metrics</h4>
            <div className="space-y-3 sm:space-y-4 text-sm">
              {/* First Row: Net APY, AUM, Investors */}
              <div className="grid grid-cols-3 gap-2 sm:gap-3">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <img src="/hedge_fund/upward trend.svg" alt="Net APY" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
                  <div className="flex flex-col">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Net APY</p>
                    <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.netApy.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <img src="/hedge_fund/Wallet.svg" alt="AUM" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
                  <div className="flex flex-col">
                    <p className="text-[10px] sm:text-xs text-zinc-500">AUM</p>
                    <span className="font-semibold text-sm sm:text-base text-white">
                      ${strategyMetrics.aum.toFixed(2)}{strategyMetrics.aumUnit}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <img src="/hedge_fund/Investors.svg" alt="Investors" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
                  <div className="flex flex-col">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Investors</p>
                    <span className="font-semibold text-sm sm:text-base text-white">
                      {strategyMetrics.participants >= 1000 
                        ? `${(strategyMetrics.participants / 1000).toFixed(1)}k` 
                        : strategyMetrics.participants.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>

              <Separator className="bg-zinc-700" />

              {/* Second Row: Sharpe, Max Drawdown, Lock-in */}
              <div className="grid grid-cols-3 gap-2 sm:gap-3">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <img src="/hedge_fund/Sharpe ratio.svg" alt="Sharpe" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
                  <div className="flex flex-col">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Sharpe</p>
                    <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.sharpe.toFixed(3)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <img src="/hedge_fund/downward trend.svg" alt="Max Drawdown" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
                  <div className="flex flex-col">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Max Drawdown</p>
                    <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.maxDrawdown.toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <img src="/hedge_fund/Lock in period.svg" alt="Lock-in" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
                  <div className="flex flex-col">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Lock-in</p>
                    <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.lockInPeriod}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>

        <CardFooter className="relative p-3 sm:p-4 flex flex-col gap-2 sm:gap-3 mt-auto">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between w-full gap-2 text-xs sm:text-sm text-zinc-400">
            
            {strategyMetrics.riskGrade && ['A', 'B', 'C'].includes(strategyMetrics.riskGrade) && (
              <img
                src={`/hedge_fund/Risk ${strategyMetrics.riskGrade}.svg`}
                alt={`Risk: ${strategyMetrics.riskGrade}`}
                className="h-6 sm:h-7 w-auto"
              />
            )}
          </div>
          <div className="flex gap-2 w-full">
            <button
              className="flex-1 hover:opacity-80 transition-opacity duration-200"
              onClick={openDepositModal}
            >
              <img src="/hedge_fund/Deposit.svg" alt="Deposit" className="w-full h-auto" />
            </button>
            <button
              className={cn(
                "flex-1 transition-opacity duration-200",
                parseFloat(strategyBalance) === 0
                  ? "opacity-40 cursor-not-allowed"
                  : "hover:opacity-80"
              )}
              onClick={openWithdrawModal}
              disabled={parseFloat(strategyBalance) === 0}
            >
              <img src="/hedge_fund/Withdraw.svg" alt="Withdraw" className="w-full h-auto" />
            </button>
          </div>
        </CardFooter>
      </Card>

      <StrategyModal
        visible={showModal}
        onClose={closeModal}
        action={modalAction}
        strategyName={strategyName}
        strategyBalance={strategyBalance}
        usdcBalance={usdcBalanceState}
        onDeposit={handleDeposit}
        onWithdraw={handleWithdraw}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
        price={priceInUSDC || undefined}
        pricePerShare={undefined}
        walletAddress={walletAddress}
        tokenAddress={config?.token_address || config?.vault_address}
        vaultAddress={config?.vault_address}
      />
    </>
  );
};

export default StrategyCard;

