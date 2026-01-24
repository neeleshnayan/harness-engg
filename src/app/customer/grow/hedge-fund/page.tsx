"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { getAuth, signOut } from "firebase/auth";
import { ArrowLeft, CheckCircle, AlertCircle, SlidersHorizontal } from "lucide-react";
import api, { hedgeFundApi } from "@/lib/api";
import StrategyCard from "@/components/wallet/StrategyCard";

import { CumulativeAUMChartNew } from "@/components/wallet/CumulativeAUMChartNew";
import { useYearnWETHConfig } from "@/hooks/useStrategyConfig";
import { SubgraphAnalyticsYearnWETH } from "@/components/wallet/SubgraphAnalyticsYearnWETH";
import { SubgraphAnalyticsGeneric } from "@/components/wallet/SubgraphAnalyticsGeneric";
import { TradingSignals } from "@/components/wallet/TradingSignals";
import { Toaster } from "@/components/ui/toaster";
import { HedgeFundForm } from "@/lib/types";
import HedgeFundQuestionnaire from "@/components/HedgeFundQuestionnaire";
import MiniHedgeFundChat from '@/components/MiniHedgeFundChat';
import WalletHeader from "@/components/wallet/WalletHeader";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import { getFirebaseApp } from "@/lib/firebaseClient";
import { AddStrategyModal } from "@/components/wallet/AddStrategyModal";

type StrategyView = 'overview' | 'yearn-weth';

export default function HedgeFundV2Page() {
  const router = useRouter();
  const { data: yearnWethConfig, isLoading: yearnWethConfigLoading } = useYearnWETHConfig();
  const [selectedView, setSelectedView] = useState<StrategyView | 'detail'>('overview');
  const [selectedStrategy, setSelectedStrategy] = useState<any>(null);
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
      return { yearnWeth: undefined, usdc: undefined };
    }

    let balances = balance.tokenBalances.filter((tokenBalance: any) => {
      const amount = parseFloat(tokenBalance.amount);
      return !isNaN(amount) && amount > 0;
    });

    let yearnWethBalance: number | undefined;
    let usdcBalance: number | undefined;

    balances.forEach((tokenBalance: any) => {
      const symbol = tokenBalance.token.symbol;
      const rawAmount = parseFloat(tokenBalance.amount || "0");

      if (symbol === 'ysWETH' || symbol === 'YEARN_WETH') {
        yearnWethBalance = (yearnWethBalance || 0) + rawAmount;
      } else if (symbol === 'USDC') {
        usdcBalance = (usdcBalance || 0) + rawAmount;
      }
    });
    return { usdc: usdcBalance, yearnWeth: yearnWethBalance };
  }, [balance]);

  useEffect(() => {
    const storedUserData = localStorage.getItem('userData');
    if (storedUserData) {
      const parsedData = JSON.parse(storedUserData);
      setUserData(parsedData);
      setAccountData(parsedData);

      // Fetch balance if wallet address exists
      if (parsedData.wallet_address) {
        fetchBalance(parsedData.wallet_address);
      }

      // Check if user has already submitted a questionnaire
      if (parsedData?.user_id) {
        // checkExistingSubmission(parsedData.user_id);
      }
    }
  }, []);

  const fetchBalance = async (address: string) => {
    try {
      setBalanceLoading(true);
      setBalanceError(null);
      const response = await api.get(`/api/v1/wallet_balance/${address}`);
      setBalance(response.data);
    } catch (err) {
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
        setShowDashboard(true); // Show dashboard if user has completed questionnaire

        // Pre-populate form with existing data
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

    // Validate all fields are filled
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
        submission_id: existingSubmission?.id, // Include submission ID for updates
        ...formData
      });

      if (response.status === 200 || response.status === 201) {
        // Check if user has already submitted
        if (response.data.status === "already_submitted") {
          setError("You have already submitted a hedge fund questionnaire. Please contact support if you need to update your responses.");
          setTimeout(() => {
            router.push('/customer/grow');
          }, 5000);
        } else {
          setSuccess(true);
          setShowDashboard(true); // Show dashboard after successful submission
          setTimeout(() => {
            setSuccess(false);
          }, 3000);
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to submit questionnaire. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const RadioGroup = ({
    title,
    field,
    options
  }: {
    title: string;
    field: keyof HedgeFundForm;
    options: { value: string; label: string }[]
  }) => (
    <div className="mb-8 p-6 bg-zinc-900/50 rounded-xl border border-zinc-700/50">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {options.map((option) => (
          <label key={option.value} className="flex items-center p-4 rounded-lg bg-zinc-800/50 hover:bg-zinc-700/50 border border-zinc-700/50 cursor-pointer transition-all duration-200">
            <input
              type="radio"
              name={field}
              value={option.value}
              checked={formData[field] === option.value}
              onChange={(e) => handleInputChange(field, e.target.value)}
              className="w-5 h-5 text-blue-500 bg-zinc-700 border-zinc-600 focus:ring-blue-500 focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-900"
            />
            <span className="ml-4 text-zinc-300 group-hover:text-white transition-colors">
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  );

  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const totalFields = Object.keys(formData).length;
    const filledFields = Object.values(formData).filter(value => value !== "").length;
    setProgress((filledFields / totalFields) * 100);
  }, [formData]);

  if (success) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
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
            className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold py-4 px-8 rounded-xl transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (balanceLoading) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">
            Loading balance...
          </p>
        </div>
      </div>
    );
  }

  const renderStrategyDetail = () => {
    switch (selectedView) {
      case 'yearn-weth':
      case 'detail':
        const currentStrategy = selectedStrategy || (selectedView === 'yearn-weth' ? strategies.find(s => s.id === 'YEARN_WETH') : null);
        const displayName = currentStrategy?.name || "Strategy Details";
        const subgraphUrl = currentStrategy?.subgraph_url || yearnWethConfig?.subgraph_url || process.env.NEXT_PUBLIC_SUBGRAPH_URL;
        const stratNameKey = currentStrategy?.id || "YEARN_WETH";

        return (
          <>
            <div className="mb-6 sm:mb-8 px-4">
              <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-2 drop-shadow-lg">
                {displayName}
              </h1>
              <p className="text-zinc-400 text-sm sm:text-base md:text-lg max-w-3xl">
                {currentStrategy?.description || "Real-time on-chain analytics and trading data."}
              </p>
            </div>

            {/* Trading Signals Section */}
            <div className="px-4 mb-6">
              <TradingSignals
                strategyName={stratNameKey}
                assetSymbol="USDC"
                targetSymbol={currentStrategy?.symbol || "WETH"}
                assetAddress={currentStrategy?.asset_address}
                targetAddress={currentStrategy?.target_address}
              />
            </div>

            {/* Subgraph Analytics */}
            {yearnWethConfigLoading && selectedView === 'yearn-weth' ? (
              <div className="text-center text-zinc-400">Loading configuration...</div>
            ) : (
              // Reuse SubgraphAnalyticsYearnWETH as generic analytics component if possible, 
              // or rename it later. Pass dynamic subgraph URL.
              <SubgraphAnalyticsGeneric
                subgraphUrl={subgraphUrl}
                strategyAddress={currentStrategy?.address}
                strategyName={displayName}
                assetSymbol="USDC" // Defaulting to USDC as base for now
                targetSymbol={currentStrategy?.symbol || "WETH"} // Use strategy symbol if available
              />
            )}
          </>
        );

      default:
        return (
          <>
            {/* Portfolio Performance Chart */}
            {accountData?.wallet_address && (
              <div className="w-full max-w-6xl mx-auto mb-4">
                <CumulativeAUMChartNew
                  userWalletAddress={accountData.wallet_address}

                  yearnWethCurrentBalance={tokenBalances.yearnWeth}
                  strategies={strategies}
                />
              </div>
            )}

            <section id="clark-chat" className="w-full max-w-6xl mx-auto mb-4 relative">
              <MiniHedgeFundChat userId={accountData?.user_id} />
            </section>

            {/* Strategy Cards */}
            <div className="w-full max-w-6xl mx-auto mb-8 sm:mb-12 px-4">
              <h2 className="text-xl sm:text-2xl font-bold text-white mb-4 sm:mb-6">Available Strategies</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
                <StrategyCard
                  strategyName="YEARN_WETH"
                  onRefresh={() => accountData?.wallet_address && fetchBalance(accountData.wallet_address)}
                  onCardClick={() => setSelectedView('yearn-weth')}
                  usdcBalance={tokenBalances.usdc?.toString()}
                />
              </div>
            </div>
          </>
        );
    }
  };

  // FETCH STRATEGIES (Moved to top)

  const { AddStrategyModal } = require("@/components/wallet/AddStrategyModal"); // Dynamic require to avoid cycle if needed, or better use top imports? Using top import is safer but modifying file is hard.
  // Actually, I should request import at top. But for now I will rely on standard imports.
  // Wait, I cannot use require inside component body in standard React/Next without issues usually.
  // I will add import at top in a separate step or just assume I add it.

  return (
    <>
      <Toaster />
      {/* Add Strategy Modal (Need to import at top!) */}
      {/* Implemented below in return structure */}
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden">
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
        />
        {showQuestionnaire && (
          <HedgeFundQuestionnaire
            onComplete={() => setShowQuestionnaire(false)}
            onClose={() => setShowQuestionnaire(false)}
            showBackButton={true}
          />
        )}
        <div className="container mx-auto px-4 py-8 max-w-7xl">
          {/* Header with Back Button */}
          {selectedView !== 'overview' && (
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
              <button
                onClick={() => setSelectedView('overview')}
                className="bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-4 sm:px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-xs sm:text-sm flex items-center justify-center w-full sm:w-auto"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Strategies
              </button>
            </div>
          )}

          {/* Header */}
          {selectedView === 'overview' && (
            <>
              {/* V1 Header retained content would go here if needed, but implementation above handles it via WalletHeader */}
            </>
          )}

          {/* Content */}
          {/* Render Detail View */}
          {(selectedView === 'yearn-weth' || selectedView === 'detail') && renderStrategyDetail()}

          {/* Render Overview (Grid) */}
          {selectedView === 'overview' && (
            <>
              {/* Portfolio Performance Chart */}
              {accountData?.wallet_address && (
                <div className="w-full max-w-6xl mx-auto mb-4">
                  <CumulativeAUMChartNew
                    userWalletAddress={accountData.wallet_address}
                    yearnWethCurrentBalance={tokenBalances.yearnWeth}
                    strategies={strategies}
                  />
                </div>
              )}

              <section id="clark-chat" className="w-full max-w-6xl mx-auto mb-4 relative">
                <MiniHedgeFundChat userId={accountData?.user_id} />
              </section>

              {/* Strategy Cards */}
              <div className="w-full max-w-6xl mx-auto mb-8 sm:mb-12 px-4">
                <div className="flex justify-between items-center mb-4 sm:mb-6">
                  <h2 className="text-xl sm:text-2xl font-bold text-white">Available Strategies</h2>
                  {/* OPTIONAL: Add Strategy Button Here too? */}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">

                  {/* 1. LEGACY YEARN WETH CARD (Keep if not in DB, else remove) */}
                  {/* We can mix them or rely on DB. Let's keep specific one if needed, but DB is better. */}
                  {/* Assuming DB has YEARN_WETH, we loop dynamic strategies */}

                  {strategies.map((strat) => (
                    <StrategyCard
                      key={strat.id || strat.address}
                      strategyName={strat.address || strat.id || "Unknown"} // Use Address or ID as Name
                      strategyData={strat}
                      onRefresh={() => {
                        accountData?.wallet_address && fetchBalance(accountData.wallet_address);
                        fetchStrategies(); // Refresh list/data
                      }}
                      onCardClick={() => {
                        setSelectedStrategy(strat);
                        setSelectedView('detail');
                        window.scrollTo(0, 0);
                      }}
                      usdcBalance={tokenBalances.usdc?.toString()}
                    />
                  ))}

                  {/* ADD STRATEGY BUTTON */}
                  <div
                    onClick={() => setShowAddStrategyModal(true)}
                    className="flex flex-col items-center justify-center h-full min-h-[300px] border-2 border-dashed border-zinc-700 hover:border-blue-500 rounded-xl bg-zinc-900/30 hover:bg-zinc-900/50 cursor-pointer transition-all group"
                  >
                    <div className="w-16 h-16 rounded-full bg-zinc-800 group-hover:bg-blue-500/20 flex items-center justify-center mb-4 transition-all">
                      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-zinc-400 group-hover:text-blue-500"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-300 group-hover:text-white">Add New Strategy</h3>
                    <p className="text-sm text-zinc-500 mt-2 text-center px-4">Deploy a new Yearn Strategy to the platform</p>
                  </div>

                </div>
              </div>

              {/* Modal */}
              {/* We must assume AddStrategyModal is imported at top. I will use a separate Tool call to add import if I can't do it here easily (I can't reliably replace top of file in same chunk easily without context). */}
              <AddStrategyModal
                isOpen={showAddStrategyModal}
                onClose={() => setShowAddStrategyModal(false)}
                onSuccess={() => {
                  fetchStrategies();
                }}
              />
            </>
          )}

        </div>
      </div>
    </>
  );
}