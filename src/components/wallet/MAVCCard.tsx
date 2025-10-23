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
    fetchBalances(true);
    
    const interval = setInterval(() => {
      fetchBalances(false);
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const fetchBalances = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true);
        setError(null);
      }
      
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        if (parsedData.wallet_address) {
          // Fetch wallet balances (includes both USDC and MAVC tokens)
          try {
            const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            console.log('Wallet Balance Response:', walletResponse.data);

            // The API returns tokenBalances array
            if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
              // Find USDC tokens (also merge TRNSK which is treated as USDC)
              const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
                b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
              );

              if (allUSDCTokens.length > 0) {
                const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                  return sum + parseFloat(token.amount || "0");
                }, 0);
                setUsdcBalance(totalUSDC.toString());
                console.log('USDC Balance set to:', totalUSDC);
              } else {
                setUsdcBalance("0");
                console.log('No USDC or TRNSK token found');
              }

              // Find MAVC tokens
              const mavcToken = walletResponse.data.tokenBalances.find((b: any) =>
                b.token && b.token.symbol === 'MAVC'
              );

              if (mavcToken) {
                // MAVC has 6 decimals - convert from Wei to human-readable format
                const rawAmount = parseFloat(mavcToken.amount || "0");
                const decimals = mavcToken.token?.decimals || 6;
                const humanReadable = rawAmount / Math.pow(10, decimals);

                setMavcBalance(humanReadable.toString());
                console.log('MAVC Balance converted:', rawAmount, '/', Math.pow(10, decimals), '=', humanReadable);
              } else {
                setMavcBalance("0");
                console.log('No MAVC token found in wallet');
              }
            } else {
              setUsdcBalance("0");
              setMavcBalance("0");
              console.warn('Invalid response format - no tokenBalances array');
            }
          } catch (err) {
            console.warn('Wallet balances not available:', err);
            setUsdcBalance("0");
            setMavcBalance("0");
          }
        }
      }
    } catch (err: any) {
      console.error('Error fetching balances:', err);
      if (showLoading) {
        setError('Failed to fetch balances');
      }
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  const handleDeposit = async (amount: string) => {
    console.log('🚀 handleDeposit called with amount:', amount);
    try {
      console.log('💰 Setting transaction loading state...');
      setTransactionLoading(true);
      setTransactionError(null);
      
      console.log('📱 Getting user data from localStorage...');
      const userData = localStorage.getItem('userData');
      console.log('👤 User data:', userData);
      
      if (!userData) {
        console.error('❌ No user data found!');
        throw new Error('User data not found');
      }
      
      const parsedData = JSON.parse(userData);
      console.log('✅ Parsed user data:', parsedData);
      
      if (!parsedData.wallet_address) {
        console.error('❌ No wallet address in user data!');
        throw new Error('Wallet address not found');
      }
      
      const payload = {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      };
      
      console.log('📤 MAVC Deposit Request Payload:', payload);
      
      // Step 1: Approve USDC for vault
      console.log('🔓 Step 1: Approving USDC for vault...');
      const approveResponse = await api.post('/api/v1/mavc/approve', payload);
      console.log('✅ Approval Response:', approveResponse.data);
      
      if (approveResponse.data.status !== 'success') {
        throw new Error('USDC approval failed');
      }
      
      setTransactionSuccess(`Approval submitted! Now depositing...`);
      
      // Wait a moment for approval to be broadcast
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Step 2: Deposit to vault
      console.log('💰 Step 2: Depositing to vault...');
      const response = await api.post('/api/v1/mavc/deposit', payload);
      
      console.log('📥 Deposit Response Status:', response.status);
      console.log('📥 Deposit Response Data:', response.data);
      
      if (response.data.status === 'success') {
        const depositTxId = response.data.deposit_tx;
        
        console.log('✅ Deposit transaction created:', depositTxId);
        
        const successMessage = `Successfully deposited ${amount} USDC to MAVC! Transaction will process on-chain.`;
        console.log('🎉 Setting success message:', successMessage);
        setTransactionSuccess(successMessage);
        console.log('🎉 Success message set! transactionSuccess should now be:', successMessage);
        
        if (onRefresh) onRefresh();
        setTimeout(() => {
          fetchBalances(false);
        }, 1000);
      } else {
        throw new Error(response.data.message || 'Deposit failed');
      }
    } catch (err: any) {
      console.error('❌ MAVC Deposit Error:', err);
      console.error('❌ Error Response:', err.response?.data);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to deposit to MAVC vault';
      console.error('❌ Setting error message:', errorMsg);
      setTransactionError(errorMsg);
    } finally {
      console.log('🏁 Finally block: Setting transactionLoading to false');
      setTransactionLoading(false);
      console.log('🏁 Finally block complete');
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
      
      const payload = {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      };
      
      console.log('MAVC Withdraw Request:', payload);
      
      const response = await api.post('/api/v1/mavc/withdraw', payload);
      
      console.log('📤 Withdraw Response:', response.data);
      
      if (response.data.status === 'success') {
        const redeemTxId = response.data.redeem_tx;
        
        console.log('✅ Withdrawal transaction created:', redeemTxId);
        
        setTransactionSuccess(`Successfully withdrew ${amount} MAVC tokens! Transaction will process on-chain.`);
        
        if (onRefresh) onRefresh();
        setTimeout(() => {
          fetchBalances();
        }, 1000);
      } else {
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('MAVC Withdraw Error:', err);
      console.error('Error Response:', err.response?.data);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to withdraw from MAVC vault';
      setTransactionError(errorMsg);
    } finally {
      setTransactionLoading(false);
    }
  };

  const openDepositModal = () => {
    console.log('🎯 Opening Deposit Modal');
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
              {parseFloat(mavcBalance).toFixed(2)} MAVC
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
        usdcBalance={usdcBalance}
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
