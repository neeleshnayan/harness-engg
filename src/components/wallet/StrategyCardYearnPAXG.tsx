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
import { useStrategyConfig } from "@/hooks/useStrategyConfig";
import { useStrategyPrice } from "@/hooks/useStrategyPrice";
import { useStrategySubgraphData } from "@/hooks/useStrategySubgraphData";
import { BalanceStatusIndicator, BalanceTransactionStage, BalanceTransactionType } from "./BalanceStatusIndicator";
import StrategyModal from "./StrategyModal";

interface StrategyCardYearnPAXGProps {
  onRefresh?: () => void;
  onCardClick?: () => void;
}

const StrategyCardYearnPAXG: React.FC<StrategyCardYearnPAXGProps> = ({ onRefresh, onCardClick }) => {
  const router = useRouter();
  const { toast } = useToast();
  const strategyName = 'YEARN_PAXG';

  const { data: config, isLoading: configLoading } = useStrategyConfig(strategyName);
  const { data: priceData, isLoading: priceLoading, error: priceError } = useStrategyPrice(
    strategyName,
    config?.subgraph_url
  );
  const { data: subgraphData, isLoading: subgraphLoading } = useStrategySubgraphData(strategyName, config?.subgraph_url);

  const [strategyBalance, setStrategyBalance] = useState("0");
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);
  const [transactionStage, setTransactionStage] = useState<BalanceTransactionStage>('idle');
  const [transactionType, setTransactionType] = useState<BalanceTransactionType>('deposit');

  // Calculate net supply from subgraph
  const netSupply = useMemo(() => {
    const metric = subgraphData?.yearnPaxgStrategyMetric;
    if (!metric) return 0;
    const minted = Number(metric.mintedShares ?? '0');
    const burned = Number(metric.burnedShares ?? '0');
    return minted - burned;
  }, [subgraphData]);

  // Calculate AUM dynamically
  const calculatedAUM = useMemo(() => {
    if (!priceData?.price || netSupply === 0) {
      return { value: config?.aum ?? 0.01, unit: '' };
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
  }, [netSupply, priceData, config?.aum]);

  const uniqueDepositors = subgraphData?.yearnPaxgStrategyMetric?.uniqueDepositors ?? config?.participants ?? 5;

  // Strategy metrics from config
  const strategyMetrics = {
    name: 'YEARN PAXG',
    description: config?.description ?? 'Yearn V3 strategy trading USDC/PAXG based on keeper signals with Uniswap V3 swaps.',
    netApy: config?.net_apy ?? 12.5,
    aum: calculatedAUM.value,
    aumUnit: calculatedAUM.unit,
    sharpe: config?.sharpe_ratio ?? 0.65,
    maxDrawdown: config?.max_drawdown ?? 15.0,
    lockInPeriod: 'None',
    participants: uniqueDepositors,
    performanceFee: config?.performance_fee ?? 10.0,
    riskGrade: config?.risk_grade ?? 'B'
  };

  const gradeStyles = {
    A: 'bg-green-500/20 text-green-400 border-green-500/20 hover:bg-green-500/30',
    B: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/30',
    C: 'bg-orange-500/20 text-orange-400 border-orange-500/20 hover:bg-orange-500/30',
    D: 'bg-red-500/20 text-red-400 border-red-500/20 hover:bg-red-500/30',
  };

  const fetchBalances = async () => {
    setBalanceLoading(true);
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        if (parsedData.wallet_address) {
          setWalletAddress(parsedData.wallet_address);

          // Fetch USDC balance
          try {
            console.log(`[YEARN_PAXG] Fetching wallet balance for:`, parsedData.wallet_address);
            const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            console.log(`[YEARN_PAXG] Wallet Response:`, walletResponse.data);
            const tokenBalances = walletResponse.data.tokenBalances || walletResponse.data.token_balances;

            if (tokenBalances && Array.isArray(tokenBalances)) {
              // Explicitly look for USDC tokens
              const allUSDCTokens = tokenBalances.filter((b: any) =>
                b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
              );
              console.log("[YEARN_PAXG] USDC Tokens Found:", allUSDCTokens);

              if (allUSDCTokens.length > 0) {
                const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                  return sum + parseFloat(token.amount || "0");
                }, 0);
                console.log("[YEARN_PAXG] Total USDC Balance:", totalUSDC);
                setUsdcBalance(totalUSDC.toString());
              } else {
                console.warn("[YEARN_PAXG] No USDC tokens found in wallet response");
                // FALLBACK: If API doesn't identify ticker, sum up based on address match?
                // For now, assume API returns correct symbol.
                setUsdcBalance("0");
              }
            } else {
              console.warn("[YEARN_PAXG] No token balances array in response");
              setUsdcBalance("0");
            }
          } catch (err) {
            console.error("[YEARN_PAXG] Failed to fetch USDC balance:", err);
            setUsdcBalance("0");
          }

          // Fetch strategy balance
          try {
            const balanceResponse = await api.get(`/api/v1/strategy/${strategyName}/balance/${parsedData.wallet_address}`);

            if (balanceResponse.data) {
              const balance_wei = balanceResponse.data.balance || "0";
              const contract_decimals = 6; // balanceResponse.data.decimals || 18;
              const balanceNum = parseFloat(balance_wei) / Math.pow(10, contract_decimals);
              setStrategyBalance(balanceNum.toString());
            } else {
              setStrategyBalance("0");
            }
          } catch (err: any) {
            console.error("[YEARN_PAXG] Failed to fetch strategy balance:", err);
            setStrategyBalance("0");
          }
        }
      }
    } catch (err: any) {
      console.error("[YEARN_PAXG] Critical error in fetchBalances:", err);
    } finally {
      setBalanceLoading(false);
    }
  };

  useEffect(() => {
    // Fetch balances even if config is loading, to debug
    fetchBalances();
  }, [config]); // Re-fetch when config loads, but also run initially

  // Handle buy (Deposit equiv for YEARN_PAXG)
  const handleBuy = async (amount: string) => {
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

      // Convert USDC amount to wei (18 decimals for YEARN_PAXG Mock USDC)
      const amountFloat = parseFloat(amount);
      const usdcDecimals = 6; // Real USDC has 6 decimals
      const amountWei = Math.floor(amountFloat * Math.pow(10, usdcDecimals)).toString();

      // Step 1: Approve
      setTransactionStage('approving');
      const approveResponse = await api.post(`/api/v1/strategy/${strategyName}/approve`, {
        amount: amountWei,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
      });

      const approveTxId = approveResponse.data.transaction_id;
      if (!approveTxId) throw new Error("Failed to get approval transaction ID");

      // Step 2: Deposit
      setTransactionStage('confirming');
      const response = await api.post(`/api/v1/strategy/${strategyName}/deposit`, {
        amount: amountWei,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
        approve_tx_id: approveTxId,
      });

      if (response.data.status === 'success') {
        setTransactionStage('success');
        await fetchBalances();
        if (onRefresh) onRefresh();
        toast({
          title: "✅ Deposit Successful",
          description: `Successfully deposited ${amount} USDC into YEARN_PAXG`,
        });
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || `Failed to buy ysPAXG`;
      setTransactionError(errorMsg);
      setTransactionStage('error');
      toast({
        title: "❌ Buy Failed",
        description: errorMsg,
      });
    } finally {
      setTransactionLoading(false);
    }
  };

  // Handle sell (Withdraw equiv for YEARN_PAXG)
  const handleSell = async (amount: string) => {
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

      // Convert token amount to wei (6 decimals for Yearn PAXG/USDC strategy)
      const amountFloat = parseFloat(amount);
      const decimals = 6;
      const amountWei = Math.floor(amountFloat * Math.pow(10, decimals)).toString();

      const response = await api.post(`/api/v1/strategy/${strategyName}/sell`, {
        amount: amountWei,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id,
      });

      if (response.data.status === 'success') {
        setTransactionStage('success');
        await fetchBalances();
        if (onRefresh) onRefresh();
        toast({
          title: "✅ Sell Successful",
          description: `Successfully swapped ${amount} ysPAXG for USDC`,
        });
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || `Failed to sell ysPAXG`;
      setTransactionError(errorMsg);
      setTransactionStage('error');
      toast({
        title: "❌ Sell Failed",
        description: errorMsg,
      });
    } finally {
      setTransactionLoading(false);
    }
  };

  const openBuyModal = (e: React.MouseEvent) => {
    e.stopPropagation();
    setModalAction('deposit');
    setShowModal(true);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  const openSellModal = (e: React.MouseEvent) => {
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
    if (onCardClick) {
      onCardClick();
    } else {
      router.push('/customer/grow/hedge-fund-v2/yearn-paxg');
    }
  };

  return (
    <>
      <Card
        className="flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl hover:-translate-y-1 bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50 cursor-pointer"
        onClick={handleCardClick}
      >
        <CardHeader className="pb-3 sm:pb-4">
          <div className="flex flex-col sm:flex-row justify-between items-start gap-3 sm:gap-4">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg sm:text-xl text-white">{strategyMetrics.name}</CardTitle>
            </div>
            <div className="flex flex-col items-start sm:items-end gap-1 w-full sm:w-auto">
              {balanceLoading || configLoading ? (
                <div className="flex items-center gap-2 px-3 py-1 rounded-lg border bg-zinc-700/20 border-zinc-700/30">
                  <div className="animate-spin rounded-full h-3 w-3 border-2 border-zinc-400 border-t-transparent"></div>
                  <span className="text-sm font-semibold text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-white to-purple-300 animate-shimmer whitespace-nowrap">
                    ••• ysPAXG
                  </span>
                </div>
              ) : (
                <BalanceStatusIndicator
                  stage={transactionStage}
                  type={transactionType}
                  balance={formatTokenBalance(strategyBalance)}
                  showShimmer={transactionStage === 'confirming'}
                  error={transactionError}
                  tokenSymbol="ysPAXG"
                />
              )}
              {/* Simplified price display logic for specific card */}
              {priceLoading ? (
                <span className="text-xs text-zinc-500 animate-pulse">Loading price...</span>
              ) : priceData?.price ? (
                <span className="text-xs text-green-400 font-medium whitespace-nowrap">
                  1 ysPAXG = ${Number(priceData.price).toFixed(2)}
                </span>
              ) : null}
            </div>
          </div>
          <CardDescription className="pt-2 text-xs sm:text-sm text-zinc-400 line-clamp-2">{strategyMetrics.description}</CardDescription>
        </CardHeader>

        <CardContent className="flex-grow space-y-4 sm:space-y-5">
          <div className="space-y-3 sm:space-y-4">
            <h4 className="text-xs sm:text-sm font-semibold text-zinc-400">Key Metrics</h4>
            <div className="space-y-3 sm:space-y-4 text-sm">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2 sm:gap-3">
                  <TrendingUp className="w-5 h-5 sm:w-6 sm:h-6 text-green-400" />
                  <div>
                    <p className="text-xs text-zinc-500">Net APY</p>
                    <span className="font-semibold text-base sm:text-lg text-white">{strategyMetrics.netApy.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 sm:gap-3 text-right">
                  <div>
                    <p className="text-xs text-zinc-500">AUM</p>
                    <span className="font-semibold text-base sm:text-lg text-white">
                      ${typeof strategyMetrics.aum === 'number' ? strategyMetrics.aum.toFixed(2) : strategyMetrics.aum}{strategyMetrics.aumUnit}
                    </span>
                  </div>
                  <Wallet className="w-5 h-5 sm:w-6 sm:h-6 text-zinc-500" />
                </div>
              </div>

              <Separator className="bg-zinc-700" />

              <div className="flex justify-between items-center text-center">
                <div className="flex flex-col items-center gap-1">
                  <BarChart className="w-4 h-4 sm:w-5 sm:h-5 text-blue-400" />
                  <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.sharpe.toFixed(2)}</span>
                  <span className="text-xs text-zinc-500">Sharpe</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <TrendingDown className="w-4 h-4 sm:w-5 sm:h-5 text-red-400" />
                  <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.maxDrawdown.toFixed(2)}%</span>
                  <span className="text-xs text-zinc-500 whitespace-nowrap">Max Drawdown</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <Clock className="w-4 h-4 sm:w-5 sm:h-5 text-zinc-500" />
                  <span className="font-semibold text-sm sm:text-base text-white">{strategyMetrics.lockInPeriod}</span>
                  <span className="text-xs text-zinc-500 whitespace-nowrap">Lock-in</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>

        <CardFooter className="p-3 sm:p-4 bg-black/20 flex flex-col gap-2 sm:gap-3 mt-auto">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between w-full gap-2 text-xs sm:text-sm text-zinc-400">
            <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-semibold text-white text-xs sm:text-sm">{strategyMetrics.participants.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <Percent className="w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-semibold text-white text-xs sm:text-sm">{strategyMetrics.performanceFee.toFixed(1)}%</span>
              </div>
            </div>
            {strategyMetrics.riskGrade && (
              <Badge className={cn("text-xs", gradeStyles[strategyMetrics.riskGrade as keyof typeof gradeStyles] || gradeStyles.D)}>
                Risk: {strategyMetrics.riskGrade}
              </Badge>
            )}
          </div>
          <div className="flex gap-2 w-full">
            <Button
              size="sm"
              className="flex-1 font-bold text-xs sm:text-sm bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700"
              onClick={openBuyModal}
            >
              <ArrowDown className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
              Buy
            </Button>
            <Button
              size="sm"
              className={cn(
                "flex-1 font-bold text-xs sm:text-sm",
                parseFloat(strategyBalance) === 0
                  ? "bg-zinc-600/50 text-zinc-400 cursor-not-allowed hover:bg-zinc-600/50"
                  : "bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700"
              )}
              onClick={openSellModal}
              disabled={parseFloat(strategyBalance) === 0}
            >
              <ArrowUp className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
              Sell
            </Button>
          </div>
        </CardFooter>
      </Card>

      <StrategyModal
        visible={showModal}
        onClose={closeModal}
        action={modalAction}
        strategyName={strategyName}
        strategyBalance={strategyBalance}
        usdcBalance={usdcBalance}
        onDeposit={handleBuy}
        onWithdraw={handleSell}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
        price={priceData?.price ? Number(priceData.price).toString() : undefined}
        walletAddress={walletAddress}
        tokenAddress={config?.token_address}
        vaultAddress={config?.vault_address}
      />
    </>
  );
};

export default StrategyCardYearnPAXG;
