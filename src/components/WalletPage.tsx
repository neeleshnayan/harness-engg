'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authManager } from '@/lib/auth';
import api from '@/lib/api';
import WalletHeader from './wallet/WalletHeader';
import BalanceCard from './wallet/BalanceCard';
import UsernameCard from './wallet/UsernameCard';
import QuickActions from './wallet/QuickActions';
import TransactionHistory from './wallet/TransactionHistory';
import SendUSDCModal from './wallet/SendUSDCModal';
import TransakWidgetModal from './wallet/TransakWidgetModal';

interface UserData {
  user_id: number;
  email: string;
  username?: string;
  wallet_id?: string;
  wallet_address?: string;
  blockchain?: string;
}

export default function WalletPage() {
  const [userData, setUserData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showSendModal, setShowSendModal] = useState(false);
  const [showBuyModal, setShowBuyModal] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const checkAuth = async () => {
      // Check if user is authenticated
      if (!authManager.isAuthenticated()) {
        router.push('/');
        return;
      }

      try {
        // Load user data from localStorage
        const storedUserData = localStorage.getItem('userData');
        if (storedUserData) {
          setUserData(JSON.parse(storedUserData));
        }

        // Verify token with backend
        await api.post('/api/v1/auth/verify-token');
      } catch (error) {
        console.error('Authentication error:', error);
        authManager.logout();
        router.push('/');
        return;
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [router]);

  const handleSendUSDC = () => {
    setShowSendModal(true);
  };

  const handleBuyCrypto = () => {
    setShowBuyModal(true);
  };

  const handleCloseSendModal = () => {
    setShowSendModal(false);
  };

  const handleCloseBuyModal = () => {
    setShowBuyModal(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-zinc-900 to-neutral-900 flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  if (!userData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-zinc-900 to-neutral-900 flex items-center justify-center">
        <div className="text-white text-xl">No user data found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-zinc-900 to-neutral-900">
      <WalletHeader 
        username={userData.username} 
        walletAddress={userData.wallet_address} 
      />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column */}
          <div className="lg:col-span-2 space-y-8">
            <BalanceCard walletAddress={userData.wallet_address} />
            <TransactionHistory username={userData.username} />
          </div>
          
          {/* Right Column */}
          <div className="space-y-8">
            <UsernameCard 
              userId={userData.user_id} 
              currentUsername={userData.username}
              onUsernameUpdate={(newUsername) => {
                setUserData(prev => prev ? { ...prev, username: newUsername } : null);
              }}
            />
            <QuickActions 
              onSendUSDC={handleSendUSDC}
              onBuyCrypto={handleBuyCrypto}
            />
          </div>
        </div>
      </div>

      {/* Modals */}
      {showSendModal && (
        <SendUSDCModal
          senderUserId={userData.user_id}
          onClose={handleCloseSendModal}
        />
      )}

      {showBuyModal && (
        <TransakWidgetModal
          walletAddress={userData.wallet_address}
          onClose={handleCloseBuyModal}
        />
      )}
    </div>
  );
} 
