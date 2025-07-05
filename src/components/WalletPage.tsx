'use client';

import React, { useState, useEffect } from "react";
import axios from "axios";
import { getAuth, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import { FaWallet, FaSignOutAlt, FaCopy, FaArrowUp, FaArrowDown } from "react-icons/fa";
import { getFirebaseApp } from "@/lib/firebaseClient";

const USDC_SVG = (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="ml-2">
    <circle cx="16" cy="16" r="16" fill="#2775CA"/>
    <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white"/>
    <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA"/>
    <text x="10" y="22" fill="white" fontSize="10" fontWeight="bold">$</text>
  </svg>
);

export default function WalletPage() {
  const [accountData, setAccountData] = useState<any>(null);
  const [balance, setBalance] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const userData = localStorage.getItem('userData');
    if (!userData) {
      router.push('/');
      return;
    }

    try {
      const data = JSON.parse(userData);
      setAccountData(data);
      if (data.wallet_address) {
        fetchBalance(data.wallet_address);
      } else {
        setError('No wallet address linked to this account.');
      }
    } catch (err) {
      console.error('Error parsing user data:', err);
      router.push('/');
    } finally {
      setLoading(false);
    }
  }, [router]);

  const fetchBalance = async (walletAddress: string) => {
    try {
      const res = await axios.get(`/api/v1/wallet_balance/${walletAddress}`);
      setBalance(res.data);
    } catch (err) {
      console.error('Error fetching balance:', err);
      setBalance(null);
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
      console.error('Error signing out:', err);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // You could add a toast notification here
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-gray-600 font-medium">Loading your wallet...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-red-600 mb-4 font-medium">{error}</p>
          <button 
            onClick={() => router.push('/')}
            className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-2xl font-medium transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center">
              <img 
                src="/krypton_logo.svg" 
                alt="Krypton Logo" 
                className="w-8 h-8 mr-3"
              />
              <h1 className="text-xl font-bold text-gray-900">Krypton Wallet</h1>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-xl transition-colors font-medium"
            >
              <FaSignOutAlt className="mr-2" />
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-gray-900 mb-2">
            Welcome back, {accountData?.email}
          </h2>
          <p className="text-gray-600">Your secure digital wallet is ready</p>
        </div>

        {/* Balance Card */}
        <div className="bg-white/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/20 mb-8">
          <div className="text-center">
            <div className="flex items-center justify-center mb-4">
              {USDC_SVG}
              <h3 className="text-2xl font-bold text-gray-900 ml-2">USDC Balance</h3>
            </div>
            <div className="text-6xl font-bold text-gray-900 mb-4">
              {(() => {
                if (balance && balance.balance && Array.isArray(balance.balance.tokenBalances) && balance.balance.tokenBalances.length > 0) {
                  const usdc = balance.balance.tokenBalances.find(
                    (b: any) => b.token && b.token.symbol === 'USDC'
                  );
                  if (usdc) {
                    return `$${usdc.amount}`;
                  }
                }
                return 'Loading...';
              })()}
            </div>
            <p className="text-gray-500 font-medium">Available for transactions</p>
          </div>
        </div>

        {/* Wallet Address Card */}
        <div className="bg-white/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/20 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold text-gray-900 flex items-center">
              <FaWallet className="mr-3 text-blue-500" />
              Wallet Address
            </h3>
            <button
              onClick={() => copyToClipboard(accountData?.wallet_address)}
              className="text-blue-500 hover:text-blue-600 transition-colors p-2 rounded-xl hover:bg-blue-50"
            >
              <FaCopy />
            </button>
          </div>
          <div className="bg-gray-50 rounded-2xl p-4">
            <p className="font-mono text-sm text-gray-700 break-all">
              {accountData?.wallet_address}
            </p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <button className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white py-6 px-8 rounded-3xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center">
            <FaArrowUp className="mr-3" />
            Send USDC
          </button>
          <button className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white py-6 px-8 rounded-3xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center">
            <FaArrowDown className="mr-3" />
            Receive USDC
          </button>
        </div>

        {/* Additional Info */}
        <div className="mt-8 text-center">
          <p className="text-gray-400 text-sm">
            Secure • Fast • Reliable
          </p>
        </div>
      </main>
    </div>
  );
} 