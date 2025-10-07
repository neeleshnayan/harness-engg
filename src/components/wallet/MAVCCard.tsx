import React, { useState, useEffect } from "react";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet } from "lucide-react";
import MAVCModal from "./MAVCModal";
import { SubgraphAnalytics } from "./SubgraphAnalytics";
import api from "@/lib/api";

interface MAVCCardProps {
  className?: string;
  onRefresh?: () => void;
  subgraphUrl?: string;
}

const MAVCCard: React.FC<MAVCCardProps> = ({ className = "", onRefresh, subgraphUrl }) => {
  const [mavcBalance, setMavcBalance] = useState("0");
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);

  // Mock data for demonstration - replace with actual API calls
  const mockData = {
    netApy: 135.3,
    aum: 8.9,
    sharpe: 0.85,
    maxDrawdown: 65.50,
    lockInPeriod: "14d",
    participants: 121,
    performanceFee: 30.0,
    riskGrade: "D" as const
  };

  useEffect(() => {
    fetchBalances();
  }, []);

  const fetchBalances = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        if (parsedData.wallet_address) {
          // Fetch MAVC balance
          try {
            const mavcResponse = await api.get(`/api/v1/mavc/balance/${parsedData.wallet_address}`);
            setMavcBalance(mavcResponse.data.balance || "0");
          } catch (err) {
            console.warn('MAVC balance not available:', err);
            setMavcBalance("0");
          }
          
          // Fetch USDC balance
          try {
            const usdcResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            const usdcBalance = usdcResponse.data.balances?.find((b: any) => b.token.symbol === 'USDC')?.amount || "0";
            setUsdcBalance(usdcBalance);
          } catch (err) {
            console.warn('USDC balance not available:', err);
            setUsdcBalance("0");
          }
        }
      }
    } catch (err: any) {
      console.error('Error fetching balances:', err);
      setError('Failed to fetch balances');
    } finally {
      setLoading(false);
    }
  };

  const pollTransactionStatus = async (txId: string, maxAttempts = 30): Promise<string> => {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const statusResponse = await api.get(`/api/v1/mavc/transaction/${txId}`);
        const transaction = statusResponse.data.transaction;
        const txStatus = transaction?.state;
        const txHash = transaction?.txHash;
        
        console.log(`🔍 Poll attempt ${i + 1}/${maxAttempts}:`, {
          txId: txId.substring(0, 8),
          status: txStatus,
          txHash: txHash,
          fullTransaction: transaction
        });
        
        if (txHash) {
          const etherscanLink = `https://sepolia.etherscan.io/tx/${txHash}`;
          setTransactionSuccess(
            `Status: ${txStatus || 'UNKNOWN'} | 🔗 View on Etherscan: ${etherscanLink} (${i + 1}/${maxAttempts})`
          );
        } else {
          setTransactionSuccess(`Checking transaction... Status: ${txStatus || 'UNKNOWN'} (${i + 1}/${maxAttempts})`);
        }
        
        if (txStatus === 'COMPLETE' || txStatus === 'CONFIRMED') {
          return 'COMPLETE';
        } else if (txStatus === 'FAILED' || txStatus === 'DENIED') {
          return 'FAILED';
        }
        
        await new Promise(resolve => setTimeout(resolve, 3000));
      } catch (err: any) {
        console.error('❌ Error polling transaction:', err);
        console.error('Error details:', err.response?.data);
        setTransactionSuccess(`Polling error (attempt ${i + 1}): ${err.message}`);
      }
    }
    return 'PENDING';
  };

  const handleDeposit = async (amount: string) => {
    try {
      setTransactionLoading(true);
      setTransactionError(null);
      
      const userData = localStorage.getItem('userData');
      if (!userData) {
        throw new Error('User data not found');
      }
      
      const parsedData = JSON.parse(userData);
      
      if (!parsedData.wallet_address) {
        throw new Error('Wallet address not found');
      }
      
      const payload = {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      };
      
      console.log('MAVC Deposit Request:', payload);
      
      const response = await api.post('/api/v1/mavc/deposit', payload);
      
      console.log('📥 Deposit Response:', response.data);
      
      if (response.data.status === 'success') {
        const depositTxId = response.data.deposit_tx;
        const approveTxId = response.data.approve_tx;
        
        console.log('✅ Transactions created:', {
          approve: approveTxId,
          deposit: depositTxId
        });
        
        setTransactionSuccess(`Transactions submitted! Approve: ${approveTxId?.substring(0, 8)}... Deposit: ${depositTxId?.substring(0, 8)}...`);
        
        const finalStatus = await pollTransactionStatus(depositTxId);
        
        if (finalStatus === 'COMPLETE') {
          setTransactionSuccess(`Successfully deposited ${amount} USDC to MAVC vault!`);
          
          if (onRefresh) onRefresh();
          await fetchBalances();
        } else if (finalStatus === 'FAILED') {
          throw new Error('Transaction failed on blockchain');
        } else {
          setTransactionSuccess(`Transaction pending. Your balance will update when it confirms on-chain.`);
        }
      } else {
        throw new Error(response.data.message || 'Deposit failed');
      }
    } catch (err: any) {
      console.error('MAVC Deposit Error:', err);
      console.error('Error Response:', err.response?.data);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to deposit to MAVC vault';
      setTransactionError(errorMsg);
    } finally {
      setTransactionLoading(false);
    }
  };

  const handleWithdraw = async (amount: string) => {
    try {
      setTransactionLoading(true);
      setTransactionError(null);
      
      const userData = localStorage.getItem('userData');
      if (!userData) {
        throw new Error('User data not found');
      }
      
      const parsedData = JSON.parse(userData);
      
      if (!parsedData.wallet_address) {
        throw new Error('Wallet address not found');
      }
      
      const response = await api.post('/api/v1/mavc/withdraw', {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      });
      
      if (response.data.status === 'success') {
        setTransactionSuccess(`Successfully withdrew ${amount} MAVC tokens!`);
        
        if (onRefresh) onRefresh();
        await fetchBalances();
      } else {
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('Error withdrawing:', err);
      setTransactionError(err.response?.data?.detail || err.message || 'Failed to withdraw from MAVC vault');
    } finally {
      setTransactionLoading(false);
    }
  };

  const openDepositModal = () => {
    setModalAction('deposit');
    setShowModal(true);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  const openWithdrawModal = () => {
    setModalAction('withdraw');
    setShowModal(true);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  const closeModal = () => {
    setShowModal(false);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  if (loading) {
    return (
      <div className={`bg-zinc-800/50 border border-zinc-700/50 rounded-2xl p-8 ${className}`}>
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
          <span className="ml-3 text-zinc-400">Loading MAVC data...</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={`bg-zinc-800/50 border border-zinc-700/50 rounded-2xl p-8 ${className}`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <div className="w-12 h-12 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center mr-4">
              <Wallet className="h-6 w-6 text-white" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white">Multi Asset Vault</h3>
              <p className="text-zinc-400 text-sm">50/50 USDC/WETH Strategy</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-xs text-zinc-400 px-2 py-1 rounded-full bg-red-900/30 text-red-400 border border-red-600/30">
              Risk: {mockData.riskGrade}
            </span>
          </div>
        </div>

        {/* Description */}
        <p className="text-zinc-400 text-sm mb-6">
          High-frequency trading strategy that exploits pricing inefficiencies across exchanges.
        </p>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <div className="text-sm text-zinc-400 mb-1">Net APY</div>
            <div className="flex items-center">
              <TrendingUp className="h-4 w-4 text-green-400 mr-2" />
              <span className="text-2xl font-bold text-white">{mockData.netApy}%</span>
            </div>
          </div>
          <div>
            <div className="text-sm text-zinc-400 mb-1">AUM</div>
            <div className="flex items-center">
              <Wallet className="h-4 w-4 text-zinc-400 mr-2" />
              <span className="text-2xl font-bold text-white">${mockData.aum}M</span>
            </div>
          </div>
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center">
            <div className="text-xs text-zinc-400 mb-1">Sharpe</div>
            <div className="text-lg font-semibold text-white">{mockData.sharpe}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-zinc-400 mb-1">Max Drawdown</div>
            <div className="flex items-center justify-center">
              <TrendingDown className="h-3 w-3 text-red-400 mr-1" />
              <span className="text-lg font-semibold text-white">{mockData.maxDrawdown}%</span>
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-zinc-400 mb-1">Lock-in Period</div>
            <div className="text-lg font-semibold text-white">{mockData.lockInPeriod}</div>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-zinc-400">
            <span className="text-white font-semibold">{mockData.participants}</span> participants • 
            <span className="text-white font-semibold ml-1">{mockData.performanceFee}%</span> fee
          </div>
          <div className="flex space-x-2">
            <button
              onClick={openDepositModal}
              className="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white rounded-lg font-semibold text-sm transition-all duration-200 flex items-center"
            >
              <ArrowDown className="h-4 w-4 mr-1" />
              Deposit
            </button>
            <button
              onClick={openWithdrawModal}
              className="px-4 py-2 bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700 text-white rounded-lg font-semibold text-sm transition-all duration-200 flex items-center"
            >
              <ArrowUp className="h-4 w-4 mr-1" />
              Withdraw
            </button>
          </div>
        </div>

        {/* Balance Display */}
        <div className="mt-4 pt-4 border-t border-zinc-700/50">
          <div className="flex justify-between items-center">
            <span className="text-sm text-zinc-400">Your MAVC Balance:</span>
            <span className="text-lg font-semibold text-white">
              {parseFloat(mavcBalance).toFixed(6)} MAVC
            </span>
          </div>
        </div>
      </div>

      {/* Subgraph Analytics */}
      <SubgraphAnalytics subgraphUrl={subgraphUrl} />

      {/* Modal */}
      <MAVCModal
        visible={showModal}
        onClose={closeModal}
        action={modalAction}
        mavcBalance={mavcBalance}
        onDeposit={handleDeposit}
        onWithdraw={handleWithdraw}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
      />
    </>
  );
};

export default MAVCCard;
