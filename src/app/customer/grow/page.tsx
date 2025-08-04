"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shield, Store } from "lucide-react";
import TokenBalances from "@/components/wallet/TokenBalances";
import api from "@/lib/api";

export default function CustomerGrowPage() {
  const router = useRouter();
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

  return (
    <div className="min-h-screen w-full flex flex-col bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
      <div className="container mx-auto max-w-6xl">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
            Grow Your Wealth
          </h1>
          {accountData?.username && (
            <div className="mb-4">
              <p className="text-zinc-400 text-lg">
                Welcome back, <span className="text-purple-400 font-semibold">@{accountData.username}</span>
              </p>
            </div>
          )}
          {/* <p className="text-zinc-400 text-lg mb-8 text-center max-w-xl mx-auto">
            Explore exclusive investment opportunities tailored for you.
          </p> */}
        </div>

        {/* Token Portfolio Section */}
        <div className="mb-12">
          <TokenBalances
            balance={balance}
            loading={balanceLoading}
            error={balanceError}
            className="mb-8"
            onRefresh={() => accountData?.wallet_address && fetchBalance(accountData.wallet_address)}
          />
        </div>

        {/* Investment Options */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-white mb-6">Investment Opportunities</h2>
          {/* <p className="text-zinc-400 text-lg mb-8">
            Choose how you want to grow your portfolio
          </p> */}
        </div>

        <div className="flex flex-col md:flex-row gap-8 w-full max-w-4xl mx-auto justify-center">
          <button
            className="flex-1 bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-cyan-400/10 hover:border-cyan-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-cyan-400"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
            onClick={() => router.push('/customer/grow/hedge-fund')}
          >
            <div className="w-16 h-16 rounded-full bg-cyan-400/20 flex items-center justify-center mb-6 group-hover:bg-cyan-400/30 transition-all">
              <Shield className="h-10 w-10 text-cyan-300 group-hover:text-cyan-400 transition-all" />
            </div>
            <span className="text-2xl font-bold text-white mb-2">Hedge Fund</span>
            <span className="text-zinc-400 text-base text-center">
              Access actively managed investment strategies to help grow and protect your assets.
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
            <span className="text-2xl font-bold text-white mb-2">Private Marketplace</span>
            <span className="text-zinc-400 text-base text-center">
              Discover exclusive deals and private market assets not available to the public.
            </span>
          </button>
        </div>

        {/* Back to Wallet Button */}
        <div className="text-center mt-12">
          <button
            onClick={() => router.push('/customer')}
            className="bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-8 py-3 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200"
          >
            ← Back to Wallet
          </button>
        </div>
      </div>
    </div>
  );
} 