import React from "react";
import TransactionHistory from "@/components/wallet/TransactionHistory";

interface BalanceCardProps {
  balance: any;
  error: string | null;
  accountData: any;
  showTransactions: boolean;
  setShowTransactions: (show: boolean) => void;
  className?: string;
  transactionHistoryRefresh?: boolean;
}

const USDC_SVG = (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="ml-2">
    <circle cx="16" cy="16" r="16" fill="#2775CA"/>
    <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white"/>
    <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA"/>
    <text x="10" y="22" fill="white" fontSize="10" fontWeight="bold">$</text>
  </svg>
);

const BalanceCard: React.FC<BalanceCardProps> = ({ balance, error, accountData, showTransactions, setShowTransactions, className, transactionHistoryRefresh }) => {
  return (
    <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 mb-8 ${className || ''}`}>
      <div className="text-center">
        <div className="flex items-center justify-center mb-4">
          {USDC_SVG}
          <h3 className="text-2xl font-bold text-white ml-2">USDC Balance</h3>
        </div>
        <div className="text-6xl font-bold text-white mb-4">
          {error ? (
            <span className="text-red-400 text-2xl font-semibold">{error}</span>
          ) : (() => {
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
        <p className="text-zinc-400 font-medium">Available for transactions</p>
        {/* Transaction History Toggle */}
        {accountData?.username && (
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