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

      // Use the new subgraph API endpoint
      const kryptonWeb3ApiUrl = process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'http://localhost:8001';
      const response = await fetch(`${kryptonWeb3ApiUrl}/subgraph/user/${address}/balances`);

      if (!response.ok) {
        throw new Error(`Failed to fetch balance: ${response.statusText}`);
      }

      const subgraphResponse = await response.json();

      // Transform subgraph response to frontend format
      const transformedBalance = {
        tokenBalances: subgraphResponse.balances.map((balance: any) => ({
          amount: balance.balance.toString(),
          token: {
            name: balance.symbol === "USDC"
              ? "USD Coin"
              : balance.symbol.startsWith("k")
              ? `Krypton ${balance.symbol.substring(1).toUpperCase()}`
              : balance.symbol,
            blockchain: "ETH-SEPOLIA",
            decimals: balance.decimals,
            isNative: balance.symbol === "ETH" || balance.symbol === "ETH-SEPOLIA",
            symbol: balance.symbol,
            tokenAddress: balance.address,
            standard: (balance.symbol === "ETH" || balance.symbol === "ETH-SEPOLIA") ? undefined : "ERC20",
          },
        })),
      };

      setBalance(transformedBalance);
    } catch (err) {
      console.error('Failed to fetch balance from subgraph:', err);
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
            className="hover:opacity-70 transition-opacity duration-200"
            aria-label="Back to Wallet"
          >
            <img
              src="/hedge_fund/Back icon.svg"
              alt="Back"
              className="h-8 w-8"
            />
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
                Hello, <span className="font-semibold" style={{ color: '#90E7EE' }}>@{accountData.username}</span>
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
            className="relative flex-1 rounded-[44px] p-8 flex flex-col items-center justify-center overflow-hidden hover:opacity-90 transition-all duration-200 group focus:outline-none"
            onClick={() => router.push('/customer/grow/hedge-fund')}
          >
            <img
              src="/hedge_fund/Big glass BG .svg"
              alt=""
              className="absolute inset-0 w-full h-full object-cover pointer-events-none"
            />
            <div className="relative w-20 h-20 flex items-center justify-center mb-6">
              <img
                src="/hedge_fund/BG circle icon for Sharktank and Hedge fund.svg"
                alt=""
                className="absolute inset-0 w-full h-full"
              />
              <Shield className="relative h-10 w-10 text-white" />
            </div>
            <span className="relative text-2xl font-bold text-white mb-2">Krypton Fund</span>
            <span className="relative text-base text-center" style={{ color: '#9A9797' }}>
              {getHedgeFundDescription()}
            </span>
          </button>
          <button
            className="relative flex-1 rounded-[44px] p-8 flex flex-col items-center justify-center overflow-hidden hover:opacity-90 transition-all duration-200 group focus:outline-none"
            onClick={() => router.push('/customer/grow/marketplace')}
          >
            <img
              src="/hedge_fund/Big glass BG .svg"
              alt=""
              className="absolute inset-0 w-full h-full object-cover pointer-events-none"
            />
            <div className="relative w-20 h-20 flex items-center justify-center mb-6">
              <img
                src="/hedge_fund/BG circle icon for Sharktank and Hedge fund.svg"
                alt=""
                className="absolute inset-0 w-full h-full"
              />
              <Store className="relative h-10 w-10 text-white" />
            </div>
            <span className="relative text-2xl font-bold text-white mb-2">Sharktank 3.0</span>
            <span className="relative text-base text-center" style={{ color: '#9A9797' }}>
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