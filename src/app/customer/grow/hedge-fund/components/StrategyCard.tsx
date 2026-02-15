"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn, formatTokenBalance } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { hedgeFundApi } from "@/lib/api";
import { useTransactionWebhook } from "@/contexts/TransactionWebhookContext";
import { StrategyName, useStrategyConfig } from "@/hooks/useStrategyConfig";
import { useStrategyPrice } from "@/hooks/useStrategyPrice";
import { useStrategySubgraphData } from "@/hooks/useStrategySubgraphData";
import { useYearnAUM } from "@/hooks/useYearnAUM";
import { ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import { BalanceStatusIndicator, BalanceTransactionStage, BalanceTransactionType } from "./BalanceStatusIndicator";
import StrategyModal from "./StrategyModal";

interface StrategyCardProps {
  strategyName: string;
  onRefresh?: () => void;
  onCardClick?: () => void;
  usdcBalance?: string;
  strategyBalance?: string;
  strategyBalanceWei?: string;
  strategyData?: any;
}

export function calculateRiskGrade(sharpeRatio: number, maxDrawdownPercent: number): string {
  const dd = Math.abs(maxDrawdownPercent);
  if (sharpeRatio >= 2.0 && dd <= 10) return "A";
  if (sharpeRatio >= 1.5 && dd <= 15) return "A-";
  if (sharpeRatio >= 1.0 && dd <= 20) return "B+";
  if (sharpeRatio >= 0.5 && dd <= 30) return "B";
  if (sharpeRatio >= 0.0 && dd <= 40) return "C";
  return "D";
}

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
  const { waitForTransaction } = useTransactionWebhook();

  const safeStrategyName = strategyName || "";

  const strategyDetails = STRATEGY_DETAILS__LEGACY[safeStrategyName] || {
    tokenSymbol: strategyData?.symbol || 'TOKEN',
    routePath: `/customer/grow/hedge-fund-v2/${safeStrategyName.toLowerCase()}`,
    metricField: 'strategyMetric',
    useTokenDetection: false,
  };

  const { data: config_fetched, isLoading: configLoading_fetched } = useStrategyConfig(strategyName as StrategyName);

  const config = strategyData || config_fetched;
  const configLoading = strategyData ? false : configLoading_fetched;

  const subgraphUrl = config?.subgraph_url || config?.SUBGRAPH_URL || process.env.NEXT_PUBLIC_SUBGRAPH_URL;
  const strategyAddress = config?.address || config?.vault_address || config?.VAULT_ADDRESS;

  const { data: priceData, isLoading: priceLoading, error: priceError } = useStrategyPrice(
    strategyName,
    subgraphUrl
  );
  const { data: subgraphData } = useStrategySubgraphData(strategyName, subgraphUrl, strategyAddress);
  const { data: yearnAUM } = useYearnAUM(strategyName);

  const [strategyBalance, setStrategyBalance] = useState("0");
  const [strategyBalanceWei, setStrategyBalanceWei] = useState("0");
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [usdcBalanceState, setUsdcBalance] = useState("0");
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);
  const [transactionStage, setTransactionStage] = useState<BalanceTransactionStage>('idle');
  const [transactionType, setTransactionType] = useState<BalanceTransactionType>('deposit');

  const calculatedAUM = useMemo(() => {
    const metric = subgraphData?.strategyMetric;
    let aumInUSD = Number(metric?.currentAum || 0);
    if (aumInUSD === 0 && metric) {
      const supply = Number(metric.currentSupply || 0);
      const sharePrice = Number(metric.lastSharePrice || 0);
      if (supply > 0 && sharePrice > 0) {
        aumInUSD = supply * sharePrice;
      }
    }
    if (aumInUSD === 0 && metric) {
      const deposited = Number(metric.totalDeposits || 0);
      const withdrawn = Number(metric.totalWithdrawals || 0);
      if (deposited > 0) {
        aumInUSD = deposited - withdrawn;
      }
    }

    if (aumInUSD >= 1_000_000) {
      return { value: aumInUSD / 1_000_000, unit: 'M' };
    } else if (aumInUSD >= 1_000) {
      return { value: aumInUSD / 1_000, unit: 'K' };
    } else {
      return { value: aumInUSD, unit: '' };
    }
  }, [subgraphData]);

  const uniqueDepositors = subgraphData?.strategyMetric?.uniqueDepositors ?? 0;

  const computed = subgraphData?.computedMetrics;

  const sharpe = computed?.sharpeRatio ?? config?.sharpe_ratio ?? 0;
  const maxDrawdown = computed?.maxDrawdown ?? config?.max_drawdown ?? 0;
  const riskGrade =
    typeof sharpe === "number" && typeof maxDrawdown === "number" && isFinite(sharpe) && isFinite(maxDrawdown)
      ? calculateRiskGrade(sharpe, Math.abs(maxDrawdown))
      : (config?.risk_grade ?? "B");

  const strategyMetrics = {
    name: config?.name || safeStrategyName || "Strategy",
    description: config?.description ?? "",
    netApy: computed?.netApy ?? config?.net_apy ?? 0,
    aum: calculatedAUM.value,
    aumUnit: calculatedAUM.unit,
    sharpe,
    maxDrawdown,
    lockInPeriod: config?.lock_in_period ?? "None",
    participants: uniqueDepositors,
    performanceFee: config?.performance_fee ?? 0,
    riskGrade,
  };

  const gradeStyles: Record<string, string> = {
    A: "bg-green-500/20 text-green-400 border-green-500/20 hover:bg-green-500/30",
    "A-": "bg-green-500/15 text-green-400/90 border-green-500/20",
    "B+": "bg-emerald-500/15 text-emerald-400/90 border-emerald-500/20",
    B: "bg-yellow-500/20 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/30",
    C: "bg-orange-500/20 text-orange-400 border-orange-500/20 hover:bg-orange-500/30",
    D: "bg-red-500/20 text-red-400 border-red-500/20 hover:bg-red-500/30",
  };

  const fetchBalances = async () => {
    setBalanceLoading(true);
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        if (parsedData.wallet_address) {
          setWalletAddress(parsedData.wallet_address);

          if (typeof usdcBalance !== 'undefined') {
            setUsdcBalance(usdcBalance);
          }
          if (typeof strategyBalanceProp !== 'undefined') {
            setStrategyBalance(strategyBalanceProp);
          }
          if (typeof strategyBalanceWeiProp !== 'undefined') {
            setStrategyBalanceWei(strategyBalanceWeiProp);
          }
        }
      }
    } catch (err: any) {
      console.error(`Error initializing ${strategyName}:`, err);
    } finally {
      setBalanceLoading(false);
    }
  };

  useEffect(() => {
    if (config) {
      fetchBalances();
    }
  }, [config]);

  useEffect(() => {
    if (typeof usdcBalance !== 'undefined') {
      setUsdcBalance(usdcBalance);
    }
  }, [usdcBalance]);

  useEffect(() => {
    if (typeof strategyBalanceProp !== 'undefined') {
      setStrategyBalance(strategyBalanceProp);
    }
    if (typeof strategyBalanceWeiProp !== 'undefined') {
      setStrategyBalanceWei(strategyBalanceWeiProp);
    }
  }, [strategyBalanceProp, strategyBalanceWeiProp]);

  const priceInUSDC = useMemo(() => {
    if (!priceData?.price) return null;
    return Number(priceData.price).toFixed(2);
  }, [priceData]);

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

      const initialBalance = parseFloat(strategyBalance);

      const amountFloat = parseFloat(amount);
      const decimals = config?.asset_decimals || 6;
      const amountWei = Math.floor(amountFloat * Math.pow(10, decimals)).toString();

      const approveResponse = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/approve`, {
        amount: amountWei,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
      });

      if (!approveResponse.data.transaction_id && !approveResponse.data.approve_tx) {
        throw new Error('Approval transaction ID not returned');
      }

      const approveTxId = approveResponse.data.transaction_id || approveResponse.data.approve_tx;
      setTransactionStage('confirming');

      await new Promise(resolve => setTimeout(resolve, 5000));

      const depositResponse = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/deposit`, {
        amount: amountWei,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
        approve_tx_id: approveTxId,
      });

      if (depositResponse.data.status === 'success') {
        const depositTxId = depositResponse.data.deposit_tx;

        if (!depositTxId) {
          throw new Error('Deposit transaction ID not returned');
        }

        try {
          await waitForTransaction(depositTxId);
        } catch (webhookErr) {
          console.warn(`Webhook wait failed for ${depositTxId}:`, webhookErr);
        }

        let balanceAttempts = 0;
        const maxBalanceAttempts = 15;

        const pollBalance = async (): Promise<void> => {
          balanceAttempts++;
          try {
            const balanceResponse = await hedgeFundApi.get(
              `/api/v1/strategy/${strategyName}/balance/${parsedData.wallet_address}`
            );

            if (balanceResponse.data) {
              const balance_wei = balanceResponse.data.balance || "0";
              const contract_decimals = balanceResponse.data.decimals || 18;
              const currentBalance = parseFloat(balance_wei) / Math.pow(10, contract_decimals);

              if (currentBalance > initialBalance + 0.0001 || balanceAttempts >= maxBalanceAttempts) {
                setStrategyBalance(currentBalance.toString());
                setStrategyBalanceWei(balance_wei);
                setTransactionStage('success');
                if (onRefresh) onRefresh();
                return;
              }
            }
          } catch (error) {
            console.error('Balance poll error:', error);
          }

          if (balanceAttempts < maxBalanceAttempts) {
            await new Promise(r => setTimeout(r, 2000));
            return pollBalance();
          }
        };

        await pollBalance();
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || `Failed to deposit to ${strategyName}`;
      setTransactionError(errorMsg);
      setTransactionStage('error');
      toast({
        title: "Deposit Failed",
        description: errorMsg,
      });
    } finally {
      setTransactionLoading(false);
    }
  };

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

      const initialBalance = parseFloat(strategyBalance);

      let amountToSend = "0";

      if (amount === strategyBalance && strategyBalanceWei && strategyBalanceWei !== "0") {
          amountToSend = strategyBalanceWei;
      } else {
          const amountFloat = parseFloat(amount);
          let decimals = 18;
          if (config?.asset_decimals === 6) {
              decimals = 6;
          } else {
              decimals = config?.share_decimals || config?.asset_decimals || 18;
          }
          
          const calculatedWeiCtx = Math.floor(amountFloat * Math.pow(10, decimals)).toString();
          
          if (strategyBalanceWei && strategyBalanceWei !== "0") {
             try {
                 const calcBI = BigInt(calculatedWeiCtx);
                 const balanceBI = BigInt(strategyBalanceWei);
                 
                 if (calcBI >= balanceBI) {
                      const maxBalFloat = parseFloat(strategyBalance);
                      if (amountFloat < maxBalFloat * 0.95) {
                          amountToSend = calculatedWeiCtx;
                      } else {
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
        const withdrawTxId = response.data.redeem_tx || response.data.withdraw_tx || response.data.transaction_id;

        if (!withdrawTxId) {
          throw new Error('Withdraw transaction ID not returned');
        }

        try {
          await waitForTransaction(withdrawTxId);
        } catch (webhookErr) {
          console.warn(`Webhook wait failed for ${withdrawTxId}:`, webhookErr);
        }

        let balanceAttempts = 0;
        const maxBalanceAttempts = 15;

        const pollBalance = async (): Promise<void> => {
          balanceAttempts++;
          try {
            const balanceResponse = await hedgeFundApi.get(
              `/api/v1/strategy/${strategyName}/balance/${parsedData.wallet_address}`
            );

            if (balanceResponse.data) {
              const balance_wei = balanceResponse.data.balance || "0";
              const contract_decimals = balanceResponse.data.decimals || 18;
              const currentBalance = parseFloat(balance_wei) / Math.pow(10, contract_decimals);

              if (currentBalance < initialBalance - 0.0001 || balanceAttempts >= maxBalanceAttempts) {
                setStrategyBalance(currentBalance.toString());
                setStrategyBalanceWei(balance_wei);
                setTransactionStage('success');
                if (onRefresh) onRefresh();
                return;
              }
            }
          } catch (error) {
            console.error('Balance poll error:', error);
          }

          if (balanceAttempts < maxBalanceAttempts) {
            await new Promise(r => setTimeout(r, 2000));
            return pollBalance();
          }
        };

        await pollBalance();
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || `Failed to withdraw from ${strategyName}`;
      setTransactionError(errorMsg);
      setTransactionStage('error');
      toast({
        title: "Withdrawal Failed",
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
        className="min-w-0 flex flex-col bg-transparent bg-no-repeat bg-cover bg-center backdrop-blur-3xl rounded-2xl sm:rounded-3xl p-0 shadow-xl border border-white/[0.08] transition-all duration-300 overflow-hidden hover:border-white/[0.12]"
        style={{ backgroundImage: "url('/wallet-bg.svg')" }}
        onClick={handleCardClick}
      >
        <CardHeader className="relative p-4 sm:p-5 pb-2 sm:pb-3 min-h-[11rem] sm:min-h-[12rem] flex flex-col">
          <div className="flex flex-row justify-between items-start gap-3">
            <CardTitle className="text-base sm:text-lg lg:text-xl text-white line-clamp-2 break-words flex-1 min-w-0 pr-2">{strategyMetrics.name}</CardTitle>
            {strategyMetrics.riskGrade && (
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium flex-shrink-0 border",
                  gradeStyles[strategyMetrics.riskGrade] ?? "bg-zinc-500/20 text-zinc-400 border-zinc-500/20"
                )}
              >
                Risk: {strategyMetrics.riskGrade}
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-col items-start gap-1 w-full">
            {balanceLoading || configLoading ? (
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg border bg-zinc-700/20 border-zinc-700/30">
                <div className="animate-spin rounded-full h-3 w-3 border-2 border-zinc-400 border-t-transparent"></div>
                <span className="text-xs sm:text-sm font-medium text-zinc-400 whitespace-nowrap">
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
              <span className="text-xs text-zinc-500">Price unavailable</span>
            ) : priceInUSDC ? (
              <span className="text-xs text-zinc-400 font-medium whitespace-nowrap">
                1 {strategyDetails.tokenSymbol} = ${priceInUSDC}
              </span>
            ) : null}
          </div>
          <CardDescription className="pt-1.5 text-xs sm:text-sm text-zinc-300 line-clamp-3 leading-relaxed break-words">{strategyMetrics.description}</CardDescription>
        </CardHeader>

        <CardContent className="relative flex-grow px-4 pb-4 pt-2 sm:px-5 sm:pb-5 sm:pt-3">
          <div className="space-y-1.5 sm:space-y-2">
            <h4 className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Key Metrics</h4>
            <div className="space-y-1.5 sm:space-y-2 text-xs sm:text-sm">
              <div className="grid grid-cols-3 gap-1.5 sm:gap-3 min-w-0">
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <img src={strategyMetrics.netApy >= 0 ? "/hedge_fund/upward trend.svg" : "/hedge_fund/downward trend.svg"} alt="Net APY" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0 opacity-70" />
                  <div className="flex flex-col min-w-0">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Net APY</p>
                    <span className="font-medium text-xs sm:text-sm text-zinc-100 truncate">{strategyMetrics.netApy.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <img src="/hedge_fund/Wallet.svg" alt="AUM" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0 opacity-70" />
                  <div className="flex flex-col min-w-0">
                    <p className="text-[10px] sm:text-xs text-zinc-500">AUM</p>
                    <span className="font-medium text-xs sm:text-sm text-zinc-100 truncate">
                      ${strategyMetrics.aum.toFixed(2)}{strategyMetrics.aumUnit}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <img src="/hedge_fund/Investors.svg" alt="Investors" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0 opacity-70" />
                  <div className="flex flex-col min-w-0">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Investors</p>
                    <span className="font-medium text-xs sm:text-sm text-zinc-100 truncate">
                      {strategyMetrics.participants >= 1000 
                        ? `${(strategyMetrics.participants / 1000).toFixed(1)}k` 
                        : strategyMetrics.participants.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>

              <Separator className="bg-white/[0.06]" />

              <div className="grid grid-cols-3 gap-1.5 sm:gap-3 min-w-0">
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <img src="/hedge_fund/Sharpe ratio.svg" alt="Sharpe" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0 opacity-70" />
                  <div className="flex flex-col min-w-0 overflow-hidden">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Sharpe</p>
                    <span className="font-medium text-xs sm:text-sm text-zinc-100 truncate">{strategyMetrics.sharpe.toFixed(2)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <img src={strategyMetrics.maxDrawdown >= 0 ? "/hedge_fund/upward trend.svg" : "/hedge_fund/downward trend.svg"} alt="Max Drawdown" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0 opacity-70" />
                  <div className="flex flex-col min-w-0 overflow-hidden">
                    <p className="text-[10px] sm:text-xs text-zinc-500" title="Max Drawdown">Max DD</p>
                    <span className="font-medium text-xs sm:text-sm text-zinc-100 truncate">{strategyMetrics.maxDrawdown.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <img src="/hedge_fund/Lock in period.svg" alt="Lock-in" className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0 opacity-70" />
                  <div className="flex flex-col min-w-0 overflow-hidden">
                    <p className="text-[10px] sm:text-xs text-zinc-500">Lock-in</p>
                    <span className="font-medium text-xs sm:text-sm text-zinc-100 truncate">{strategyMetrics.lockInPeriod}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>

        <CardFooter className="relative px-4 pb-4 pt-3 sm:px-5 sm:pb-5 flex flex-col gap-2 mt-auto border-t border-white/5">
          <div className="flex gap-2 w-full">
            <button
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full bg-gradient-to-r from-teal-800/90 to-teal-700/70 hover:from-teal-700/90 hover:to-teal-600/70 text-teal-100 text-sm font-semibold transition-all duration-200 border border-teal-600/30"
              onClick={openDepositModal}
            >
              <ArrowDownToLine className="w-4 h-4 flex-shrink-0 text-teal-300" />
              Deposit
            </button>
            <button
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full bg-transparent hover:bg-white/5 text-zinc-300 hover:text-zinc-100 text-sm font-semibold transition-all duration-200 border border-white/20 hover:border-white/30",
                parseFloat(strategyBalance) === 0
                  ? "opacity-40 cursor-not-allowed"
                  : ""
              )}
              onClick={openWithdrawModal}
              disabled={parseFloat(strategyBalance) === 0}
            >
              <ArrowUpFromLine className="w-4 h-4 flex-shrink-0" />
              Withdraw
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
