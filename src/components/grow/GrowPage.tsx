"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shield, Store } from "lucide-react";
import TokenBalances from "@/components/wallet/TokenBalances";
// Removed unused useMAVCConfig import
import api from "@/lib/api";

interface GrowPageProps {
  userType: 'business' | 'customer';
  backRoute: string;
}

export default function GrowPage({ userType, backRoute }: GrowPageProps) {
  const router = useRouter();
  // Removed unused mavcConfig hook
  const [balance, setBalance] = useState<any>(null);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [accountData, setAccountData] = useState<any>(null);

  useEffect(() => {
    // Get user data from localStorage
    const userData = localStorage.getItem('userData');
    if (userData) {
      try {
        const data = JSON.parse(userData);
        setAccountData(data);

        // Fetch balance if wallet address exists
        if (data.wallet_address) {
          fetchBalance(data.wallet_address);
        }
      } catch (err) {
        console.error('Error parsing user data:', err);
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
      console.error('Failed to fetch balance:', err);
      setBalanceError('Failed to fetch token balances');
    } finally {
      setBalanceLoading(false);
    }
  };

  const getPageTitle = () => {
    return userType === 'business' ? 'Grow Your Business' : 'Grow Your Wealth';
  };

  const getPageDescription = () => {
    return userType === 'business'
      ? 'Explore investment opportunities and grow your business portfolio.'
      : 'Explore exclusive investment opportunities tailored for you.';
  };

  const getInvestmentDescription = () => {
    return userType === 'business'
      ? 'Choose how you want to grow your business portfolio'
      : 'Choose how you want to grow your portfolio';
  };

  const getHedgeFundDescription = () => {
    return userType === 'business'
      ? 'Access actively managed investment strategies to help grow and protect your business assets.'
      : 'Access actively managed investment strategies to help grow and protect your assets.';
  };

  return (
    <div className="min-h-screen w-full flex flex-col bg-[#001C1B] p-8">
      <div className="container mx-auto max-w-6xl">
        {/* Header with Back to Wallet Button */}
        <div className="flex justify-between items-start mb-12">
          <div className="flex-1"></div>
          <button
            onClick={() => router.push(backRoute)}
            className="bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-sm"
          >
            ← Back to Wallet
          </button>
        </div>

        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
            {getPageTitle()}
          </h1>
          {accountData?.username && (
            <div className="mb-4">
              <p className="text-zinc-400 text-lg">
                Welcome back, <span className="text-purple-400 font-semibold">@{accountData.username}</span>
              </p>
            </div>
          )}
          <p className="text-zinc-400 text-lg mb-8 text-center max-w-xl mx-auto">
            {getPageDescription()}
          </p>
        </div>

        {/* Investment Options Section */}
        <div className="flex flex-col lg:flex-row gap-8 w-full max-w-6xl mx-auto justify-center">
          <button
            className="flex-1 bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-emerald-400/10 hover:border-emerald-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-emerald-400"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
            onClick={() => router.push('/customer/grow/hedge-fund')}
          >
            <div className="w-16 h-16 rounded-full bg-emerald-400/20 flex items-center justify-center mb-6 group-hover:bg-emerald-400/30 transition-all">
              <Shield className="h-10 w-10 text-emerald-300 group-hover:text-emerald-400 transition-all" />
            </div>
            <span className="text-2xl font-bold text-white mb-2">Hedge Fund</span>
            <span className="text-zinc-400 text-base text-center">
              {getHedgeFundDescription()}
            </span>
          </button>
          <button
            className="flex-1 bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-fuchsia-400/10 hover:border-fuchsia-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
            onClick={() => router.push('/customer/grow/marketplace')}
          >
            <div className="w-16 h-16 rounded-full bg-fuchsia-400/20 flex items-center justify-center mb-6 group-hover:bg-fuchsia-400/30 transition-all">
              <Store className="h-10 w-10 text-fuchsia-300 group-hover:text-fuchsia-400 transition-all" />
            </div>
            <span className="text-2xl font-bold text-white mb-2">Sharktank 3.0</span>
            <span className="text-zinc-400 text-base text-center">
              Discover exclusive deals and private market assets not available to the public.
            </span>
          </button>
        </div>

        {/* Token Portfolio Section - Aligned with Investment Options */}
        <div className="w-full max-w-4xl mx-auto mt-12">
          <TokenBalances
            balance={balance}
            loading={balanceLoading}
            error={balanceError}
            className="mb-8"
            onRefresh={() => accountData?.wallet_address && fetchBalance(accountData.wallet_address)}
            // subgraphUrl={mavcConfig?.subgraph_url} // Removed unused prop
            userWalletAddress={accountData?.wallet_address}
          />
        </div>
      </div>
    </div>
  );
}