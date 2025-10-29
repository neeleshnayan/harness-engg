import React, { useState, useEffect, useMemo } from "react";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet } from "lucide-react";
import MAVCModal from "./MAVCModal";
import { SubgraphAnalytics } from "./SubgraphAnalytics";
import api from "@/lib/api";
import { formatTokenBalance } from "@/lib/utils";
import { useMAVCConfig } from "@/hooks/useMAVCConfig";
import { useMAVCPrice } from "@/hooks/useMAVCPrice";
import { useSubgraphData } from "@/hooks/useSubgraphData";

interface MAVCCardProps {
  className?: string;
  onRefresh?: () => void;
  subgraphUrl?: string;
}

const MAVCCard: React.FC<MAVCCardProps> = ({ className = "", onRefresh, subgraphUrl }) => {
  const { data: mavcConfig, isLoading: configLoading } = useMAVCConfig();

  // Fetch MAVC price from subgraph (updates every 60 seconds)
  const { data: mavcPriceData, isLoading: priceLoading, error: priceError } = useMAVCPrice(
    subgraphUrl || mavcConfig?.subgraph_url
  );

  // Fetch subgraph data to get net MAVC supply
  const { data: subgraphData } = useSubgraphData(subgraphUrl || mavcConfig?.subgraph_url);

  const [mavcBalance, setMavcBalance] = useState("0");
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);

  // Calculate net MAVC supply (minted - burned)
  const netMAVCSupply = useMemo(() => {
    if (!subgraphData?.vaultMetric) return 0;
    const minted = Number(subgraphData.vaultMetric.mintedShares ?? '0');
    const burned = Number(subgraphData.vaultMetric.burnedShares ?? '0');
    return minted - burned;
  }, [subgraphData]);

  // Calculate AUM dynamically: total_MAVC_supply * price_of_MAVC_in_USD
  const calculatedAUM = useMemo(() => {
    if (!mavcPriceData?.price || netMAVCSupply === 0) {
      return { value: mavcConfig?.aum ?? 8.9, unit: 'M' }; // Fallback to config value
    }
    const priceInUSD = Number(mavcPriceData.price);
    const aumInUSD = netMAVCSupply * priceInUSD;

    // Display based on magnitude
    if (aumInUSD >= 1_000_000) {
      return { value: aumInUSD / 1_000_000, unit: 'M' }; // Millions
    } else if (aumInUSD >= 1_000) {
      return { value: aumInUSD / 1_000, unit: 'K' }; // Thousands
    } else {
      return { value: aumInUSD, unit: '' }; // Raw value
    }
  }, [netMAVCSupply, mavcPriceData, mavcConfig?.aum]);

  // Get unique depositors from subgraph data
  const uniqueDepositors = subgraphData?.vaultMetric?.uniqueDepositors ?? mavcConfig?.participants ?? 121;

  // Fetch strategy metrics from database via mavcConfig
  const strategyMetrics = {
    netApy: mavcConfig?.net_apy ?? 135.3,
    aum: calculatedAUM.value,
    aumUnit: calculatedAUM.unit,
    sharpe: mavcConfig?.sharpe_ratio ?? 0.85,
    maxDrawdown: mavcConfig?.max_drawdown ?? 65.50,
    lockInPeriod: mavcConfig?.lock_in_period ?? "14d",
    participants: uniqueDepositors,
    performanceFee: mavcConfig?.performance_fee ?? 30.0,
    riskGrade: mavcConfig?.risk_grade ?? "D"
  };

  useEffect(() => {
    if (mavcConfig?.token_address) {
      fetchBalances(true);

      const interval = setInterval(() => {
        fetchBalances(false);
      }, 5000);

      return () => clearInterval(interval);
    }
  }, [mavcConfig?.token_address]);

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
          setWalletAddress(parsedData.wallet_address);
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

              // Find MAVC token by the token address from Firestore config
              const mavcTokenAddress = mavcConfig?.token_address;

              const mavcToken = mavcTokenAddress
                ? walletResponse.data.tokenBalances.find((b: any) =>
                    b.token &&
                    b.token.symbol === 'MAVC' &&
                    b.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()
                  )
                : null;

              if (mavcToken) {
                console.log('✅ FOUND MAVC Token in MAVCCard with correct address!');
                console.log('🔍 Address:', mavcToken.token?.tokenAddress);
                console.log('🔍 Amount (from API):', mavcToken.amount);
                console.log('🔍 Decimals from API:', mavcToken.token?.decimals);

                // MAVC uses 12 decimals (10^12) - convert to human-readable format
                const rawAmount = parseFloat(mavcToken.amount || "0");
                const humanReadable = rawAmount / Math.pow(10, 12);

                setMavcBalance(humanReadable.toString());
                console.log('✅ MAVC Balance converted:', rawAmount, '/ 10^12 =', humanReadable);
              } else {
                setMavcBalance("0");
                console.log('❌ No MAVC token found with correct address in MAVCCard');
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
      setTransactionSuccess(null);

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

      // Capture initial balance before transaction
      const initialMAVCBalance = parseFloat(mavcBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);
      console.log('💰 Initial MAVC Balance:', initialMAVCBalance);
      console.log('💵 Initial USDC Balance:', initialUSDCBalance);

      // Step 1: Approve USDC for vault
      console.log('🔓 Step 1: Approving USDC for vault...');
      const approveResponse = await api.post('/api/v1/mavc/approve', payload);
      console.log('✅ Approval Response:', approveResponse.data);

      if (approveResponse.data.status !== 'success') {
        throw new Error('USDC approval failed');
      }

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
        console.log('⏳ Waiting for balance to change...');

        // Poll for balance change
        const maxAttempts = 60; // 60 attempts = 2 minutes max
        let attempts = 0;
        let balanceChanged = false;

        while (attempts < maxAttempts && !balanceChanged) {
          await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds between checks

          // Fetch updated balance
          const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);

          if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
            // Check MAVC balance
            const mavcTokenAddress = mavcConfig?.token_address;
            const mavcToken = mavcTokenAddress
              ? walletResponse.data.tokenBalances.find((b: any) =>
                  b.token &&
                  b.token.symbol === 'MAVC' &&
                  b.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()
                )
              : null;

            if (mavcToken) {
              const rawAmount = parseFloat(mavcToken.amount || "0");
              const currentMAVCBalance = rawAmount / Math.pow(10, 12);
              console.log(`🔍 Attempt ${attempts + 1}: MAVC Balance = ${currentMAVCBalance} (initial: ${initialMAVCBalance})`);

              // Check if MAVC balance increased
              if (currentMAVCBalance > initialMAVCBalance) {
                console.log('✅ Balance changed! MAVC increased from', initialMAVCBalance, 'to', currentMAVCBalance);
                balanceChanged = true;

                // Update local state
                setMavcBalance(currentMAVCBalance.toString());

                // Also update USDC balance
                const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
                  b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
                );
                if (allUSDCTokens.length > 0) {
                  const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                    return sum + parseFloat(token.amount || "0");
                  }, 0);
                  setUsdcBalance(totalUSDC.toString());
                }

                const successMessage = `Successfully deposited ${amount} USDC to MAVC!`;
                setTransactionSuccess(successMessage);

                if (onRefresh) onRefresh();
              }
            }
          }

          attempts++;
        }

        if (!balanceChanged) {
          console.warn('⚠️ Balance did not change within timeout period');
          throw new Error('Transaction submitted but balance not updated yet. Please check back in a moment.');
        }
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

  // MAVC Price in USDC (fetched from subgraph, updates every 60 seconds)
  const mavcPriceInUSDC = mavcPriceData?.price
    ? formatTokenBalance(mavcPriceData.price)
    : null;

  const handleWithdraw = async (amount: string) => {
    console.log('='.repeat(80));
    console.log('🚀 MAVC WITHDRAWAL STARTED');
    console.log('='.repeat(80));
    console.log('📋 Withdrawal amount requested:', amount);

    try {
      setTransactionLoading(true);
      setTransactionError(null);
      setTransactionSuccess(null);

      const userData = localStorage.getItem('userData');
      if (!userData) {
        console.error('❌ User data not found in localStorage');
        throw new Error('User data not found');
      }

      const parsedData = JSON.parse(userData);
      console.log('✅ User data loaded:', {
        user_id: parsedData.user_id,
        wallet_address: parsedData.wallet_address,
      });

      if (!parsedData.wallet_address) {
        console.error('❌ Wallet address not found in user data');
        throw new Error('Wallet address not found');
      }

      const payload = {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      };

      console.log('📤 Sending MAVC Withdraw Request to Backend:');
      console.log('   - Amount:', payload.amount, 'MAVC');
      console.log('   - Destination Wallet:', payload.wallet_address);
      console.log('   - User ID:', payload.user_id);
      console.log('   - API Endpoint: /api/v1/mavc/withdraw');

      // Log the FULL payload for debugging
      console.log('📦 Full Request Payload:', JSON.stringify(payload, null, 2));
      console.log('🎯 KEY INFO - WITHDRAWAL WILL SEND FUNDS TO:', payload.wallet_address);

      // Capture initial balance before transaction
      const initialMAVCBalance = parseFloat(mavcBalance);
      const initialUSDCBalance = parseFloat(usdcBalance);
      console.log('💰 Initial Balances (before withdrawal):');
      console.log('   - MAVC Balance:', initialMAVCBalance);
      console.log('   - USDC Balance:', initialUSDCBalance);

      console.log('🌐 Making API call to backend...');
      const response = await api.post('/api/v1/mavc/withdraw', payload);

      console.log('✅ API call completed!');

      console.log('📨 Backend Response Received:');
      console.log('   - Status Code:', response.status);
      console.log('   - Response Data:', JSON.stringify(response.data, null, 2));

      if (response.data.status === 'success') {
        const redeemTxId = response.data.redeem_tx;
        const txState = response.data.tx_state;
        const txHash = response.data.tx_hash;
        console.log('✅ Withdrawal transaction created successfully!');
        console.log('   - Transaction ID:', redeemTxId);
        console.log('   - Transaction State:', txState);
        console.log('   - TX Hash:', txHash || 'Pending...');
        console.log('⏳ Starting balance polling (max 2 minutes)...');

        // Poll for balance change
        const maxAttempts = 60; // 60 attempts = 2 minutes max
        let attempts = 0;
        let balanceChanged = false;

        while (attempts < maxAttempts && !balanceChanged) {
          await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds between checks
          attempts++;

          console.log(`🔍 Balance Check Attempt ${attempts}/${maxAttempts}...`);

          // Fetch updated balance
          const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
          console.log(`   - Fetched wallet data for: ${parsedData.wallet_address}`);

          if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
            // Check MAVC balance (should decrease) and USDC balance (should increase)
            const mavcTokenAddress = mavcConfig?.token_address;
            const mavcToken = mavcTokenAddress
              ? walletResponse.data.tokenBalances.find((b: any) =>
                  b.token &&
                  b.token.symbol === 'MAVC' &&
                  b.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()
                )
              : null;

            // Check USDC balance
            const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
              b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
            );

            let currentMAVCBalance = 0;
            let currentUSDCBalance = 0;

            if (mavcToken) {
              const rawAmount = parseFloat(mavcToken.amount || "0");
              currentMAVCBalance = rawAmount / Math.pow(10, 12);
            }

            if (allUSDCTokens.length > 0) {
              currentUSDCBalance = allUSDCTokens.reduce((sum: number, token: any) => {
                return sum + parseFloat(token.amount || "0");
              }, 0);
            }

            console.log(`   - Current MAVC: ${currentMAVCBalance} (initial: ${initialMAVCBalance}) [${currentMAVCBalance < initialMAVCBalance ? 'DECREASED ✓' : 'NO CHANGE'}]`);
            console.log(`   - Current USDC: ${currentUSDCBalance} (initial: ${initialUSDCBalance}) [${currentUSDCBalance > initialUSDCBalance ? 'INCREASED ✓' : 'NO CHANGE'}]`);

            // Check if MAVC balance decreased OR USDC balance increased
            if (currentMAVCBalance < initialMAVCBalance || currentUSDCBalance > initialUSDCBalance) {
              console.log('✅ BALANCE CHANGED DETECTED!');
              console.log('   - MAVC:', initialMAVCBalance, '->', currentMAVCBalance);
              console.log('   - USDC:', initialUSDCBalance, '->', currentUSDCBalance);
              balanceChanged = true;

              // Update local state
              setMavcBalance(currentMAVCBalance.toString());
              setUsdcBalance(currentUSDCBalance.toString());

              const successMessage = `Successfully withdrew ${amount} MAVC tokens!`;
              setTransactionSuccess(successMessage);

              if (onRefresh) onRefresh();
              console.log('='.repeat(80));
              console.log('✅ WITHDRAWAL COMPLETED SUCCESSFULLY!');
              console.log('='.repeat(80));
            }
          }
        }

        if (!balanceChanged) {
          console.warn('='.repeat(80));
          console.warn('⚠️ TIMEOUT: Balance did not change within 2 minutes');
          console.warn('   - Transaction may still be processing on-chain');
          console.warn('   - Check Circle dashboard or block explorer');
          console.warn('   - Transaction ID:', redeemTxId);
          console.warn('='.repeat(80));
          throw new Error('Transaction submitted but balance not updated yet. Please check back in a moment.');
        }
      } else {
        console.error('❌ Backend returned non-success status:', response.data);
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('='.repeat(80));
      console.error('❌ MAVC WITHDRAWAL ERROR');
      console.error('='.repeat(80));
      console.error('Error:', err);
      console.error('Error Message:', err.message);
      console.error('Response Data:', err.response?.data);
      const errorMsg = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to withdraw from MAVC vault';
      setTransactionError(errorMsg);
    } finally {
      console.log('🏁 Finally block: Setting transactionLoading to false');
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


  if (loading || configLoading) {
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
              Risk: {strategyMetrics.riskGrade}
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
              <span className="text-2xl font-bold text-white">{strategyMetrics.netApy}%</span>
            </div>
          </div>
          <div>
            <div className="text-sm text-zinc-400 mb-1">AUM</div>
            <div className="flex items-center">
              <Wallet className="h-4 w-4 text-zinc-400 mr-2" />
              <span className="text-2xl font-bold text-white">
                ${strategyMetrics.aum.toFixed(2)}{strategyMetrics.aumUnit}
              </span>
            </div>
          </div>
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center">
            <div className="text-xs text-zinc-400 mb-1">Sharpe</div>
            <div className="text-lg font-semibold text-white">{strategyMetrics.sharpe}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-zinc-400 mb-1">Max Drawdown</div>
            <div className="flex items-center justify-center">
              <TrendingDown className="h-3 w-3 text-red-400 mr-1" />
              <span className="text-lg font-semibold text-white">{strategyMetrics.maxDrawdown}%</span>
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-zinc-400 mb-1">Lock-in Period</div>
            <div className="text-lg font-semibold text-white">{strategyMetrics.lockInPeriod}</div>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-zinc-400">
            <span className="text-white font-semibold">{strategyMetrics.participants}</span> participants •
            <span className="text-white font-semibold ml-1">{strategyMetrics.performanceFee}%</span> fee
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
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-zinc-400">Your MAVC Balance:</span>
            <span className="text-lg font-semibold text-white">
              {formatTokenBalance(mavcBalance)} MAVC
            </span>
          </div>
          {/* MAVC Price in USDC */}
          <div className="flex justify-between items-center">
            <span className="text-sm text-zinc-400">1 MAVC Price:</span>
            {priceLoading ? (
              <span className="text-sm text-zinc-500">Loading...</span>
            ) : priceError ? (
              <span className="text-sm text-red-400">Price unavailable</span>
            ) : mavcPriceInUSDC ? (
              <span className="text-sm font-medium text-green-400">
                ${mavcPriceInUSDC} USDC
              </span>
            ) : (
              <span className="text-sm text-zinc-500">--</span>
            )}
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
        mavcPrice={mavcPriceInUSDC}
        walletAddress={walletAddress}
        tokenAddress="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
      />
    </>
  );
};

export default MAVCCard;
