'use client';

import React, { useState, useEffect } from "react";
import api from "@/lib/api";

interface TransactionHistoryProps {
  username?: string;
}

interface Transaction {
  id: string;
  type: string;
  amount: string;
  status: string;
  timestamp: string;
  description: string;
}

const TransactionHistory: React.FC<TransactionHistoryProps> = ({ username }) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (username) {
      fetchTransactions();
    }
  }, [username]);

  const fetchTransactions = async () => {
    if (!username) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get(`/api/v1/latest_transactions_by_username/${username}`);
      if (response.data && Array.isArray(response.data)) {
        setTransactions(response.data);
      } else {
        setTransactions([]);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load transactions');
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  if (!username) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <h3 className="text-xl font-bold text-white mb-4">Transaction History</h3>
        <p className="text-zinc-400 text-center">Set a username to view transaction history</p>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-white">Transaction History</h3>
        <button
          onClick={fetchTransactions}
          disabled={loading}
          className="text-zinc-400 hover:text-zinc-300 transition-colors text-sm disabled:opacity-50"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
      
      {loading && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400 mx-auto mb-4"></div>
          <p className="text-zinc-400">Loading transactions...</p>
        </div>
      )}
      
      {error && (
        <div className="text-center py-8">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={fetchTransactions}
            className="text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            Try again
          </button>
        </div>
      )}
      
      {!loading && !error && transactions.length === 0 && (
        <div className="text-center py-8">
          <p className="text-zinc-400">No transactions found</p>
        </div>
      )}
      
      {!loading && !error && transactions.length > 0 && (
        <div className="space-y-4">
          {transactions.map((tx) => (
            <div
              key={tx.id}
              className="flex items-center justify-between p-4 bg-zinc-800/50 rounded-lg border border-zinc-700/50"
            >
              <div className="flex-1">
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    tx.type === 'send' ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'
                  }`}>
                    {tx.type === 'send' ? 'Sent' : 'Received'}
                  </span>
                  <span className="text-white font-medium">{tx.amount} USDC</span>
                </div>
                <p className="text-zinc-400 text-sm mt-1">{tx.description}</p>
              </div>
              <div className="text-right">
                <p className="text-zinc-500 text-xs">
                  {new Date(tx.timestamp).toLocaleDateString()}
                </p>
                <span className={`text-xs font-medium ${
                  tx.status === 'completed' ? 'text-green-400' : 'text-yellow-400'
                }`}>
                  {tx.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TransactionHistory; 