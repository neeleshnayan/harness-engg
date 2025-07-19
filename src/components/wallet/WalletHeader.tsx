import React from 'react';
import { authManager } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { LogOut, User, Wallet } from 'lucide-react';

interface WalletHeaderProps {
  username?: string;
  walletAddress?: string;
}

export default function WalletHeader({ username, walletAddress }: WalletHeaderProps) {
  const router = useRouter();

  const handleLogout = async () => {
    try {
      // Call logout endpoint
      await fetch('/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authManager.getAccessToken()}`,
        },
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage and redirect
      authManager.logout();
      router.push('/');
    }
  };

  return (
    <div className="flex items-center justify-between w-full p-4 bg-white/5 backdrop-blur-xl border-b border-white/10">
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <Wallet className="w-6 h-6 text-cyan-400" />
          <h1 className="text-xl font-bold text-white">Krypton Wallet</h1>
        </div>
      </div>
      
      <div className="flex items-center space-x-4">
        {username && (
          <div className="flex items-center space-x-2 text-white/80">
            <User className="w-4 h-4" />
            <span className="text-sm">@{username}</span>
          </div>
        )}
        
        {walletAddress && (
          <div className="hidden md:flex items-center space-x-2 text-white/60">
            <span className="text-xs font-mono">
              {walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}
            </span>
          </div>
        )}
        
        <button
          onClick={handleLogout}
          className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 hover:text-red-300 transition-all duration-200"
        >
          <LogOut className="w-4 h-4" />
          <span className="text-sm font-medium">Logout</span>
        </button>
      </div>
    </div>
  );
} 