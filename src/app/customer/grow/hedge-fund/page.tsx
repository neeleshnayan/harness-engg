"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { getAuth, signOut } from "firebase/auth";
import { CheckCircle } from "lucide-react";
import { hedgeFundApi } from "@/lib/api";

import { CumulativeAUMChartNew } from "./components/CumulativeAUMChartNew";
import { Toaster } from "@/components/ui/toaster";
import { HedgeFundForm } from "@/lib/types";
import HedgeFundQuestionnaire from "./components/HedgeFundQuestionnaire";
import MiniHedgeFundChat from '@/components/MiniHedgeFundChat';
import WalletHeader from "@/components/wallet/WalletHeader";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import { getFirebaseApp } from "@/lib/firebaseClient";
import { AddStrategyModal } from "./components/AddStrategyModal";
import { TransactionWebhookProvider } from "@/contexts/TransactionWebhookContext";
import { filterStrategies } from "./utils/strategyFilters";
import { AvailableStrategiesSection } from "./components/AvailableStrategiesSection";
import { useStrategiesWithMetrics } from "./hooks/useStrategiesWithMetrics";

export default function HedgeFundV2Page() {
  const router = useRouter();
  const [formData, setFormData] = useState<HedgeFundForm>({
    age: "",
    annualIncome: "",
    emergencyFund: "",
    investmentDropReaction: "",
    investmentStyle: "",
    marketLossExperience: "",
    portfolioComfort: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [userData, setUserData] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [existingSubmission, setExistingSubmission] = useState<any>(null);
  const [showDashboard, setShowDashboard] = useState(false);
  const [balance, setBalance] = useState<any>(null);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [accountData, setAccountData] = useState<any>(null);
  const [showQuestionnaire, setShowQuestionnaire] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  // FETCH STRATEGIES
  const [strategies, setStrategies] = useState<any[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [showAddStrategyModal, setShowAddStrategyModal] = useState(false);

  // Strategy list filters (risk + APY)
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [apyFilter, setApyFilter] = useState<string>("all");

  const { strategiesWithMetrics } = useStrategiesWithMetrics(strategies);

  const activeStrategies = useMemo(
    () => filterStrategies(strategiesWithMetrics, riskFilter, apyFilter),
    [strategiesWithMetrics, riskFilter, apyFilter]
  );

  const fetchStrategies = async () => {
    try {
      setStrategiesLoading(true);
      const res = await hedgeFundApi.get('/api/v1/strategies');
      if (res.data && res.data.data) {
        setStrategies(res.data.data);
      }
    } catch (e) {
      console.error("Failed to fetch strategies", e);
    } finally {
      setStrategiesLoading(false);
    }
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  const tokenBalances = useMemo(() => {
    if (!balance || !Array.isArray(balance.tokenBalances)) {
      return { yearnWeth: undefined, usdc: undefined, strategies: {} as Record<string, string>, strategiesWei: {} as Record<string, string> };
    }

    let balances = balance.tokenBalances.filter((tokenBalance: any) => {
      const amount = parseFloat(tokenBalance.amount);
      return !isNaN(amount) && amount > 0;
    });

    let yearnWethBalance: number | undefined;
    let usdcBalance: number | undefined;
    const strategyBalances: Record<string, string> = {};
    const strategyBalancesWei: Record<string, string> = {};

    balances.forEach((tokenBalance: any) => {
      const symbol = tokenBalance.token.symbol;
      const rawAmount = parseFloat(tokenBalance.amount || "0");

      if (symbol === 'ysWETH' || symbol === 'YEARN_WETH') {
        yearnWethBalance = (yearnWethBalance || 0) + rawAmount;
      } else if (symbol === 'USDC') {
        usdcBalance = (usdcBalance || 0) + rawAmount;
      }
    });

    // Extract strategy balances - now coming directly from batch API
    // Token symbol IS the strategy ID (YSNVDA, YSGS, KFGOLD, YSXAG)
    balances.forEach((tokenBalance: any) => {
      const symbol = tokenBalance.token.symbol;

      // Skip USDC and yearnWeth (already processed above)
      if (symbol !== 'USDC' && symbol !== 'TRNSK' && symbol !== 'ysWETH' && symbol !== 'YEARN_WETH') {
        strategyBalances[symbol] = tokenBalance.amount || "0";
        strategyBalancesWei[symbol] = tokenBalance.balanceWei || "0";
      }
    });

    return { usdc: usdcBalance, yearnWeth: yearnWethBalance, strategies: strategyBalances, strategiesWei: strategyBalancesWei };
  }, [balance]);

  useEffect(() => {
    const storedUserData = localStorage.getItem('userData');
    if (!storedUserData) return;
    try {
      const parsedData = JSON.parse(storedUserData);
      setUserData(parsedData);
      setAccountData(parsedData);

      // Fetch balance if wallet address exists
      if (parsedData?.wallet_address) {
        fetchBalance(parsedData.wallet_address);
      }
    } catch {
      // Corrupted userData - ignore
    }
  }, []);

  const fetchBalance = async (address: string) => {
    try {
      setBalanceLoading(true);
      setBalanceError(null);

      // OPTIMIZED: Single batch API call to hedge fund backend
      const response = await hedgeFundApi.get(`/api/v1/strategies/balances/${address}`);
      const batchData = response.data;
      const tokenBalances: any[] = [];

      // Add USDC balance
      if (batchData.usdc_balance && parseFloat(batchData.usdc_balance) > 0) {
        tokenBalances.push({
          amount: batchData.usdc_balance,
          token: {
            symbol: "USDC",
            address: "0x1c7d4b196cb0c7b01d743fbc6116a902379c7238" // USDC address
          }
        });
      }

      // Add strategy balances
      if (batchData.strategy_balances) {
        Object.entries(batchData.strategy_balances).forEach(([strategyId, data]: [string, any]) => {
          tokenBalances.push({
            amount: data.balance,
            balanceWei: data.balance_wei, // Capture raw wei balance
            token: {
              symbol: strategyId,
              address: data.address
            }
          });
        });
      }

      setBalance({ tokenBalances });
    } catch (err) {
      console.error("❌ Batch balance fetch failed:", err);
      setBalanceError('Failed to fetch token balances');
    } finally {
      setBalanceLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      const app = getFirebaseApp();
      if (app) {
        const auth = getAuth(app);
        await signOut(auth);
      }
      localStorage.removeItem('userData');
      router.push('/');
    } catch (err) {
      console.error('Error logging out:', err);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
  };

  const checkExistingSubmission = async (userId: string) => {
    try {
      const response = await hedgeFundApi.get(`/api/v1/hedge-fund/${userId}`);
      if (response.status === 200 && response.data.status === "success") {
        const submissionData = response.data.data;
        setExistingSubmission(submissionData);
        setIsEditing(true);
        setShowDashboard(true);
        setFormData({
            age: submissionData.age,
            annualIncome: submissionData.annualIncome,
            emergencyFund: submissionData.emergencyFund,
            investmentDropReaction: submissionData.investmentDropReaction,
            investmentStyle: submissionData.investmentStyle,
            marketLossExperience: submissionData.marketLossExperience,
            portfolioComfort: submissionData.portfolioComfort
        });
      }
    } catch (err: any) {
      setLoading(false);
    }
  };

  const handleInputChange = (field: keyof HedgeFundForm, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const requiredFields = Object.keys(formData) as (keyof HedgeFundForm)[];
    const emptyFields = requiredFields.filter(field => !formData[field]);

    if (emptyFields.length > 0) {
      setError("Please fill in all required fields");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const endpoint = isEditing ? "/api/v1/hedge-fund/update" : "/api/v1/hedge-fund/submit";
      const response = await hedgeFundApi.post(endpoint, {
        user_id: userData?.user_id,
        submission_id: existingSubmission?.id,
        ...formData
      });

      if (response.status === 200 || response.status === 201) {
        if (response.data.status === "already_submitted") {
          setError("You have already submitted a hedge fund questionnaire.");
          setTimeout(() => router.push('/customer/grow'), 5000);
        } else {
          setSuccess(true);
          setShowDashboard(true);
          setTimeout(() => setSuccess(false), 3000);
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to submit questionnaire.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#001C1B] p-4 sm:p-8">
        <div className="text-center max-w-md bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-8 shadow-2xl">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="h-10 w-10 text-green-400" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-4">All Set!</h2>
          <p className="text-zinc-400 mb-8">
            Your investment profile is complete. You can now explore personalized hedge fund strategies.
          </p>
          <button
            onClick={() => setShowDashboard(true)}
            className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold py-4 px-8 rounded-xl transition-all duration-200"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (balanceLoading) {
    return (
      <div className="min-h-screen w-full bg-[#001C1B] dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">Loading balance...</p>
        </div>
      </div>
    );
  }

  return (
    <TransactionWebhookProvider walletAddress={accountData?.wallet_address}>
      <Toaster />
      <div className="min-h-screen w-full min-w-0 bg-[#001C1B] dark overflow-x-hidden">
        <WalletHeader
          accountData={accountData}
          onLogout={handleLogout}
          onMenuToggle={() => setShowMenu(!showMenu)}
          onOpenQuestionnaire={() => setShowQuestionnaire(true)}
        />
        <HamburgerMenu
          visible={showMenu}
          onClose={() => setShowMenu(false)}
          onLogout={handleLogout}
          accountData={accountData}
          onCopyAddress={() => copyToClipboard(accountData?.wallet_address || '')}
          onOpenQuestionnaire={() => setShowQuestionnaire(true)}
        />
        {showQuestionnaire && (
          <HedgeFundQuestionnaire
            onComplete={() => setShowQuestionnaire(false)}
            onClose={() => setShowQuestionnaire(false)}
            showBackButton={true}
          />
        )}
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-5 sm:py-8 max-w-6xl min-w-0">
          {/* Portfolio Performance Chart */}
          {accountData?.wallet_address && (
            <section className="w-full mb-6 sm:mb-8">
              <CumulativeAUMChartNew
                userWalletAddress={accountData.wallet_address}
                strategies={strategies}
                balanceData={balance}
              />
            </section>
          )}

          <AvailableStrategiesSection
            strategies={strategies}
            activeStrategies={activeStrategies}
            riskFilter={riskFilter}
            apyFilter={apyFilter}
            onRiskChange={setRiskFilter}
            onApyChange={setApyFilter}
            onAddStrategy={() => setShowAddStrategyModal(true)}
            onRefresh={() => {
              accountData?.wallet_address && fetchBalance(accountData.wallet_address);
              fetchStrategies();
            }}
            tokenBalances={{
              usdc: tokenBalances.usdc,
              strategies: tokenBalances.strategies,
              strategiesWei: tokenBalances.strategiesWei,
            }}
            walletAddress={accountData?.wallet_address}
          />

          <section id="clark-chat" className="w-full pb-8">
            <MiniHedgeFundChat userId={accountData?.user_id} />
          </section>

          <AddStrategyModal
            isOpen={showAddStrategyModal}
            onClose={() => setShowAddStrategyModal(false)}
            onSuccess={() => {
              fetchStrategies();
            }}
          />

        </div>
      </div>
    </TransactionWebhookProvider>
  );
}