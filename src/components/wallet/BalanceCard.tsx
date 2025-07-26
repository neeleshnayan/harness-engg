import React from "react";
import TransactionHistory from "@/components/wallet/TransactionHistory";
import { FaShieldAlt } from "react-icons/fa";

interface BalanceCardProps {
  balance: any;
  error: string | null;
  accountData: any;
  showTransactions: boolean;
  setShowTransactions: (show: boolean) => void;
  className?: string;
  transactionHistoryRefresh?: boolean;
  kycStatus?: string | null;
  onKycClick?: () => void;
}

const USDC_SVG = (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="ml-2">
    <circle cx="16" cy="16" r="16" fill="#2775CA"/>
    <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white"/>
    <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA"/>
    <text x="10" y="22" fill="white" fontSize="10" fontWeight="bold">$</text>
  </svg>
);

const BalanceCard: React.FC<BalanceCardProps> = ({ 
  balance, 
  error, 
  accountData, 
  showTransactions, 
  setShowTransactions, 
  className, 
  transactionHistoryRefresh,
  kycStatus,
  onKycClick
}) => {
  const showKycSection = accountData?.username && kycStatus !== 'approved' && onKycClick;
  const showBalanceSection = accountData?.username && kycStatus === 'approved';
  
  // // Debug logging
  // console.log('BalanceCard Debug:', {
  //   hasUsername: !!accountData?.username,
  //   kycStatus,
  //   showKycSection,
  //   showBalanceSection,
  //   onKycClick: !!onKycClick
  // });
  
  return (
    <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 mb-8 ${className || ''}`}>
      <div className="text-center">
        <div className="flex items-center justify-center mb-4">
          {USDC_SVG}
          <h3 className="text-2xl font-bold text-white ml-2">USDC Balance</h3>
        </div>
        
        {/* Show KYC banner if username is set but KYC not approved */}
        {showKycSection && (
          <div className="mb-6">
            <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 border border-purple-500/30 rounded-2xl p-6 mb-4">
              <div className="flex items-center justify-center mb-4">
                <FaShieldAlt className="text-3xl text-purple-400 mr-3" />
                <h3 className="text-xl font-bold text-white">Complete KYC Verification</h3>
              </div>
              <p className="text-zinc-300 mb-4 text-center">
                Complete your identity verification to unlock wallet functionality and start sending payments securely.
              </p>
              <button
                onClick={onKycClick}
                className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-semibold py-3 px-8 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
              >
                <FaShieldAlt className="inline mr-2" />
                Start Verification
              </button>
              <p className="text-xs text-zinc-500 mt-3 text-center">
                Verification takes just a few minutes
              </p>
            </div>
          </div>
        )}
        
        {/* Only show balance if KYC is approved */}
        {showBalanceSection && (
          <div className="text-6xl font-bold text-white mb-4">
            {error ? (
              <span className="text-red-400 text-2xl font-semibold">{error}</span>
            ) : (() => {
              if (balance && Array.isArray(balance.tokenBalances) && balance.tokenBalances.length > 0) {
                const usdc = balance.tokenBalances.find(
                  (b: any) => b.token && b.token.symbol === 'USDC'
                );
                if (usdc) {
                  return `$${usdc.amount}`;
                }
              }
              return 'Loading...';
            })()}
          </div>
        )}
        
        {/* Show message based on status */}
        {!showBalanceSection && (
          <div className="text-2xl font-bold text-zinc-400 mb-4">
            {!accountData?.username ? 'Set username to continue' : 'Complete KYC to view balance'}
          </div>
        )}
        
        <p className="text-zinc-400 font-medium">
          {showBalanceSection ? 'Available for transactions' : 'Wallet functionality will be unlocked after verification'}
        </p>
        
        {/* Transaction History Toggle - Only show if KYC is approved */}
        {showBalanceSection && (
          <div className="mt-6 pt-4 border-t border-zinc-700/50">
            <button
              onClick={() => setShowTransactions(!showTransactions)}
              className="flex items-center justify-center space-x-2 text-zinc-400 hover:text-zinc-300 transition-colors text-sm"
            >
              <span>Transaction History</span>
              <svg
                className={`w-3 h-3 transition-transform duration-200 ${showTransactions ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {/* Transaction History Dropdown */}
            {showTransactions && (
              <div className="mt-4">
                <TransactionHistory
                  username={accountData.username}
                  userWalletAddress={accountData.wallet_address}
                  refresh={transactionHistoryRefresh}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BalanceCard; 