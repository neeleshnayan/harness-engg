"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import HedgeFundDashboard from "@/components/HedgeFundDashboard";
import StrategyCard from "@/components/wallet/StrategyCard";
import TokenBalances from "@/components/wallet/TokenBalances";
import { CumulativeAUMChartNew } from "@/components/wallet/CumulativeAUMChartNew";
import { useMAVCConfig, useMAVPConfig, useMAVCYearnConfig } from "@/hooks/useStrategyConfig";
import { SubgraphAnalytics } from "@/components/wallet/SubgraphAnalytics";
import { SubgraphAnalyticsMAVP } from "@/components/wallet/SubgraphAnalyticsMAVP";
import { SubgraphAnalyticsMAVCYearn } from "@/components/wallet/SubgraphAnalyticsMAVCYearn";
import { Toaster } from "@/components/ui/toaster";
import { HedgeFundForm } from "@/lib/types";
import HedgeFundChat from "@/components/HedgeFundChat";

type StrategyView = 'overview' | 'mavc' | 'mavp' | 'mavc-yearn';

export default function HedgeFundV2Page() {
  const router = useRouter();
  const { data: mavcConfig, isLoading: mavcConfigLoading } = useMAVCConfig();
  const { data: mavpConfig, isLoading: mavpConfigLoading } = useMAVPConfig();
  const { data: mavcYearnConfig, isLoading: mavcYearnConfigLoading } = useMAVCYearnConfig();
  const [selectedView, setSelectedView] = useState<StrategyView>('overview');
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

  const tokenBalances = useMemo(() => {
    if (!balance || !Array.isArray(balance.tokenBalances)) {
      return { mavc: undefined, mavp: undefined, mavcYearn: undefined };
    }

    let balances = balance.tokenBalances.filter((tokenBalance: any) => {
      const amount = parseFloat(tokenBalance.amount);
      return !isNaN(amount) && amount > 0;
    });

    const mavcTokenAddress = mavcConfig?.token_address;
    let mavcBalance: number | undefined;
    let mavpBalance: number | undefined;
    let mavcYearnBalance: number | undefined;

    balances.forEach((tokenBalance: any) => {
      const symbol = tokenBalance.token.symbol;
      const rawAmount = parseFloat(tokenBalance.amount || "0");

      if (symbol === 'MAVC' && mavcTokenAddress && 
          tokenBalance.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()) {
        mavcBalance = rawAmount / Math.pow(10, 12);
      } else if (symbol === 'MAVP') {
        mavpBalance = (mavpBalance || 0) + rawAmount / Math.pow(10, 12);
      } else if (symbol === 'ysMAVC' || symbol === 'ysUSDC' || symbol === 'MAVC_YEARN' || symbol === 'MAVC-YEARN') {
        mavcYearnBalance = (mavcYearnBalance || 0) + rawAmount;
      }
    });
    return { mavc: mavcBalance, mavp: mavpBalance, mavcYearn: mavcYearnBalance };
  }, [balance, mavcConfig]);

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

  const checkExistingSubmission = async (userId: string) => {
    try {
      const response = await api.get(`/api/v1/hedge-fund/${userId}`);
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
      const response = await api.post(endpoint, {
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

  if (showDashboard) {
    return <HedgeFundDashboard />;
  }

  const renderStrategyDetail = () => {
    switch (selectedView) {
      case 'mavc':
        return (
          <>
            <div className="mb-6 sm:mb-8 px-4">
              <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-2 drop-shadow-lg">
                Multi Asset Vault (MAVC)
              </h1>
              <p className="text-zinc-400 text-sm sm:text-base md:text-lg max-w-3xl">
                Real-time on-chain analytics and subgraph data for the Multi Asset Vault strategy.
              </p>
            </div>
            {mavcConfigLoading ? (
              <div className="text-center text-zinc-400">Loading configuration...</div>
            ) : (
              <SubgraphAnalytics subgraphUrl={mavcConfig?.subgraph_url} />
            )}
          </>
        );
      case 'mavp':
        return (
          <>
            <div className="mb-6 sm:mb-8 px-4">
              <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-2 drop-shadow-lg">
                Multi Asset Vault Protocol (MAVP)
              </h1>
              <p className="text-zinc-400 text-sm sm:text-base md:text-lg max-w-3xl">
                Real-time on-chain analytics and subgraph data for the Multi Asset Vault Protocol strategy.
              </p>
            </div>
            {mavpConfigLoading ? (
              <div className="text-center text-zinc-400">Loading configuration...</div>
            ) : (
              <SubgraphAnalyticsMAVP subgraphUrl={mavpConfig?.subgraph_url} />
            )}
          </>
        );
      case 'mavc-yearn':
        return (
          <>
            <div className="mb-6 sm:mb-8 px-4">
              <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-2 drop-shadow-lg">
                MAVC Yearn
              </h1>
              <p className="text-zinc-400 text-sm sm:text-base md:text-lg max-w-3xl">
                Real-time on-chain analytics and subgraph data for the MAVC Yearn strategy.
              </p>
            </div>
            {mavcYearnConfigLoading ? (
              <div className="text-center text-zinc-400">Loading configuration...</div>
            ) : (
              <SubgraphAnalyticsMAVCYearn subgraphUrl={mavcYearnConfig?.subgraph_url} />
            )}
          </>
        );
      default:
        return (
          <>
            {/* Portfolio Performance Chart */}
            {accountData?.wallet_address && (
              <div className="w-full max-w-6xl mx-auto mb-12">
                <CumulativeAUMChartNew
                  userWalletAddress={accountData.wallet_address}
                  mavcCurrentBalance={tokenBalances.mavc}
                  mavpCurrentBalance={tokenBalances.mavp}
                  mavcYearnCurrentBalance={tokenBalances.mavcYearn}
                />
              </div>
            )}

            {/* Hedge Fund Chat */}
            <section id="clark-chat" className="mb-10">
              <HedgeFundChat userId={accountData?.user_id} />
            </section>

            {/* Strategy Cards */}
            <div className="w-full max-w-6xl mx-auto mb-8 sm:mb-12 px-4">
              <h2 className="text-xl sm:text-2xl font-bold text-white mb-4 sm:mb-6">Available Strategies</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
                <StrategyCard
                  strategyName="MAVC"
                  onRefresh={() => accountData?.wallet_address && fetchBalance(accountData.wallet_address)}
                  onCardClick={() => setSelectedView('mavc')}
                />
                <StrategyCard
                  strategyName="MAVP"
                  onRefresh={() => accountData?.wallet_address && fetchBalance(accountData.wallet_address)}
                  onCardClick={() => setSelectedView('mavp')}
                />
                <StrategyCard
                  strategyName="MAVC_YEARN"
                  onRefresh={() => accountData?.wallet_address && fetchBalance(accountData.wallet_address)}
                  onCardClick={() => setSelectedView('mavc-yearn')}
                />
              </div>
            </div>
          </>
        );
    }
  };

  return (
    <>
      <Toaster />
      <div className="min-h-screen w-full flex flex-col bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-4 sm:p-6 md:p-8">
        <div className="container mx-auto max-w-7xl">
          {/* Header with Back Button */}
          <div className="flex flex-col sm:flex-row justify-between items-start gap-3 sm:gap-0 mb-6 sm:mb-8">
            {selectedView !== 'overview' ? (
              <button
                onClick={() => setSelectedView('overview')}
                className="bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-4 sm:px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-xs sm:text-sm flex items-center w-full sm:w-auto justify-center"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Strategies
              </button>
            ) : (
              <div className="flex-1"></div>
            )}
            <button
              onClick={() => router.push('/customer/grow')}
              className="bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-4 sm:px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-xs sm:text-sm w-full sm:w-auto justify-center flex items-center"
            >
              ← Back to Grow
            </button>
          </div>

          {/* Header */}
          {selectedView === 'overview' && (
            <div className="text-center mb-8 sm:mb-12 px-4">
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
                Hedge Fund V2
              </h1>
              {accountData?.username && (
                <div className="mb-4">
                  <p className="text-zinc-400 text-base sm:text-lg">
                    Welcome back, <span className="text-emerald-400 font-semibold">@{accountData.username}</span>
                  </p>
                </div>
              )}
              <p className="text-zinc-400 text-sm sm:text-base md:text-lg mb-8 text-center max-w-xl mx-auto">
                Advanced investment strategies with on-chain analytics and subgraph monitoring.
              </p>
            </div>
          )}

          {/* Content */}
          {renderStrategyDetail()}
        </div>
      </div>
    </>
  );
}

