"use client";

import React, { useState, useEffect } from "react";
import { getAuth, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import { FaWallet, FaSignOutAlt, FaCopy, FaArrowUp, FaArrowDown, FaUser, FaCheck, FaTimes, FaBars, FaShieldAlt } from "react-icons/fa";
import { getFirebaseApp } from "@/lib/firebaseClient";
import UsernameCard from "@/components/wallet/UsernameCard";
import BalanceCard from "@/components/wallet/BalanceCard";
import SendUSDCModal from "@/components/wallet/SendUSDCModal";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import QuickActions from "@/components/wallet/QuickActions";
import api from "@/lib/api";
import WalletHeader from "@/components/wallet/WalletHeader";
import SumsubKYCModal from "@/components/wallet/SumsubKYCModal";

export default function BusinessPage() {
  // --- All state and logic from WalletPage ---
  const [accountData, setAccountData] = useState<any>(null);
  const [balance, setBalance] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState<string>("");
  const [showUsernameForm, setShowUsernameForm] = useState(false);
  const [usernameLoading, setUsernameLoading] = useState(false);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [usernameSuccess, setUsernameSuccess] = useState<string | null>(null);
  const [showSendForm, setShowSendForm] = useState(false);
  const [receiverUsername, setReceiverUsername] = useState<string>("");
  const [sendAmount, setSendAmount] = useState<string>("");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [showTransactions, setShowTransactions] = useState(false);
  const [refreshingBalance, setRefreshingBalance] = useState(false);
  const [transactionHistoryRefresh, setTransactionHistoryRefresh] = useState(false);
  const [kycModalVisible, setKycModalVisible] = useState(false);
  const [kycAccessToken, setKycAccessToken] = useState<string | null>(null);
  const [kycStatus, setKycStatus] = useState<string | null>(null);
  const [kycChecking, setKycChecking] = useState(false);
  const [kycMessage, setKycMessage] = useState<string | null>(null);
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
      // Fetch fresh KYC status from backend instead of relying on localStorage
      if (data.user_id) {
        fetchUserData(data.user_id);
      }
      if (data.wallet_address) {
        fetchBalance(data.wallet_address);
      }
      // Don't show error if wallet address is missing - it will be fetched by fetchUserData
    } catch (err) {
      setError('Invalid user data.');
    } finally {
      setLoading(false);
    }
  }, [router]);

  const fetchUserData = async (userId: string) => {
    try {
      const response = await api.get(`/api/v1/user/${userId}`);
      const userData = response.data;
      setKycStatus(userData.kyc_status || 'pending');
      
      // Preserve existing wallet data if not in the response
      const currentData = accountData || {};
      const updatedData = { 
        ...currentData, 
        ...userData,
        // Ensure wallet data is preserved
        wallet_address: userData.wallet_address || currentData.wallet_address,
        wallet_id: userData.wallet_id || currentData.wallet_id,
        blockchain: userData.blockchain || currentData.blockchain,
        // Ensure user_id is preserved (Firestore returns 'id' but we need 'user_id')
        user_id: userData.id || currentData.user_id || userId
      };
      
      setAccountData(updatedData);
      localStorage.setItem('userData', JSON.stringify(updatedData));
      
      // If we have a wallet address and it's not already being fetched, fetch balance
      if (updatedData.wallet_address && !balance) {
        fetchBalance(updatedData.wallet_address);
      }
      
      // If user has username but KYC is not approved, check status
      if (updatedData.username && userData.kyc_status !== 'approved') {
        console.log('User has username but KYC not approved, checking status...');
        setTimeout(() => {
          checkKycStatus(userId);
        }, 1000);
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
      // Fallback to localStorage data
      const data = JSON.parse(localStorage.getItem('userData') || '{}');
      setKycStatus(data.kyc_status || 'pending');
    }
  };

  const fetchBalance = async (address: string) => {
    try {
      const response = await api.get(`/api/v1/wallet_balance/${address}`);
      setBalance(response.data);
    } catch (err) {
      setError('Failed to fetch balance.');
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
    } catch (err) {}
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
  };

  const handleSetUsername = async () => {
    if (!username.trim()) {
      setUsernameError("Username cannot be empty");
      return;
    }
    const cleanUsername = username.replace(/^@/, '');
    if (cleanUsername.length < 3) {
      setUsernameError("Username must be at least 3 characters long");
      return;
    }
    if (cleanUsername.length > 20) {
      setUsernameError("Username must be less than 20 characters");
      return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(cleanUsername)) {
      setUsernameError("Username can only contain letters, numbers, and underscores");
      return;
    }
    setUsernameLoading(true);
    setUsernameError(null);
    setUsernameSuccess(null);
    try {
      const response = await api.post("/api/v1/set_username", {
        user_id: accountData.user_id,
        username: cleanUsername.trim()
      });
      setUsernameSuccess(`Username set to @${cleanUsername.trim()} successfully!`);
      setShowUsernameForm(false);
      setUsername("");
      const updatedAccountData = {
        ...accountData,
        username: cleanUsername.trim()
      };
      setAccountData(updatedAccountData);
      localStorage.setItem('userData', JSON.stringify(updatedAccountData));
    } catch (err: any) {
      let errorMsg = err.response?.data?.detail || "Failed to set username";
      if (typeof errorMsg === 'object' && errorMsg !== null) {
        if (Array.isArray(errorMsg)) {
          errorMsg = errorMsg.map(e => e.msg || JSON.stringify(e)).join('; ');
        } else if (errorMsg.msg) {
        } else {
          errorMsg = JSON.stringify(errorMsg);
        }
      }
      setUsernameError(errorMsg);
    } finally {
      setUsernameLoading(false);
    }
  };

  const handleCancelUsername = () => {
    setShowUsernameForm(false);
    setUsername("");
    setUsernameError(null);
    setUsernameSuccess(null);
  };

  const handleSendUSDC = async () => {
    if (!receiverUsername.trim()) {
      setSendError("Receiver username is required");
      return;
    }
    if (!sendAmount.trim() || parseFloat(sendAmount) <= 0) {
      setSendError("Please enter a valid amount");
      return;
    }
    const amount = parseFloat(sendAmount);
    if (isNaN(amount)) {
      setSendError("Please enter a valid number");
      return;
    }
    setSendLoading(true);
    setSendError(null);
    setSendSuccess(null);
    try {
      const response = await api.post("/api/v1/send_usdc", {
        sender_user_id: accountData.user_id,
        receiver_username: receiverUsername.trim(),
        amount: amount
      });
      setSendSuccess(`Successfully sent $${amount} USDC to @${receiverUsername.trim()}`);
      setReceiverUsername("");
      setSendAmount("");
      setBalance(null);
      setRefreshingBalance(true);
      if (accountData.wallet_address) {
        fetchBalance(accountData.wallet_address);
      }
      setTransactionHistoryRefresh(prev => !prev);
    } catch (err: any) {
      let errorMsg = err.response?.data?.detail || "Failed to send USDC";
      if (typeof errorMsg === 'object' && errorMsg !== null) {
        if (Array.isArray(errorMsg)) {
          errorMsg = errorMsg.map(e => e.msg || JSON.stringify(e)).join('; ');
        } else if (errorMsg.msg) {
        } else {
          errorMsg = JSON.stringify(errorMsg);
        }
      }
      setSendError(errorMsg);
    } finally {
      setSendLoading(false);
    }
  };

  const handleCancelSend = () => {
    setShowSendForm(false);
    setReceiverUsername("");
    setSendAmount("");
    setSendError(null);
    setSendSuccess(null);
  };

  const openKycModal = async (userId: string) => {
    // 1. Create applicant if needed
    await api.post('/api/v1/kyc/applicant', { user_id: userId });
    // 2. Get access token
    const tokenRes = await api.post('/api/v1/kyc/access-token', { user_id: userId });
    setKycAccessToken(tokenRes.data.token || tokenRes.data.accessToken || tokenRes.data.access_token);
    setKycModalVisible(true);
  };

  const checkKycStatus = async (userId: string) => {
    console.log('Checking KYC status for user:', userId);
    setKycChecking(true);
    setKycMessage(null);
    try {
      const response = await api.post(`/api/v1/kyc/check-status/${userId}`);
      
      if (response.data.status === 'success') {
        const newStatus = response.data.kyc_status;
        console.log('KYC status check result:', newStatus);
        setKycStatus(newStatus);
        const updatedData = { ...accountData, kyc_status: newStatus };
        setAccountData(updatedData);
        localStorage.setItem('userData', JSON.stringify(updatedData));
        
        if (newStatus === 'approved') {
          setKycMessage('KYC verification completed successfully!');
          setTimeout(() => setKycMessage(null), 3000);
        } else if (newStatus === 'rejected') {
          setKycMessage('KYC verification was rejected. Please try again.');
          setTimeout(() => setKycMessage(null), 5000);
        } else {
          setKycMessage(`KYC status: ${newStatus}`);
          setTimeout(() => setKycMessage(null), 3000);
        }
      } else {
        setKycMessage(response.data.message || 'Failed to check KYC status');
        setTimeout(() => setKycMessage(null), 5000);
      }
    } catch (err: any) {
      console.error('Failed to check KYC status:', err);
      setKycMessage(err.response?.data?.detail || 'Failed to check KYC status');
      setTimeout(() => setKycMessage(null), 5000);
    } finally {
      setKycChecking(false);
    }
  };

  const skipKyc = async (userId: string) => {
    try {
      
      // Use accountData.id as fallback if userId is not provided
      const actualUserId = userId || accountData?.id;
      
      if (!actualUserId) {
        console.error('No user ID provided for skip KYC');
        setKycMessage('No user ID found');
        return;
      }
      
      
      // Update KYC status to approved in the backend
      const response = await api.post(`/api/v1/kyc/skip/${actualUserId}`);
      
      if (response.data.status === 'success') {
        setKycStatus('approved');
        const updatedData = { ...accountData, kyc_status: 'approved' };
        setAccountData(updatedData);
        localStorage.setItem('userData', JSON.stringify(updatedData));
        setKycMessage('KYC skipped successfully');
      } else {
        setKycMessage(response.data.message || 'Failed to skip KYC');
      }
    } catch (err: any) {
      console.error('Failed to skip KYC:', err);
      setKycMessage(err.response?.data?.detail || 'Failed to skip KYC');
    } finally {
      // Clear message after 5 seconds
      setTimeout(() => setKycMessage(null), 5000);
    }
  };

  const pollKycStatus = async (userId: string) => {
    console.log('Starting KYC status polling for user:', userId);
    // Poll user data for KYC status
    for (let i = 0; i < 15; i++) { // Increased attempts
      try {
        console.log(`Polling attempt ${i + 1}/15`);
        const res = await api.get(`/api/v1/user/${userId}`);
        const status = res.data.kyc_status;
        console.log('Current KYC status:', status);
        
        if (status === 'approved') {
          console.log('KYC approved! Updating status...');
          setKycStatus('approved');
          const updated = { ...accountData, kyc_status: 'approved' };
          setAccountData(updated);
          localStorage.setItem('userData', JSON.stringify(updated));
          setKycMessage('KYC verification completed successfully!');
          // Clear success message after 3 seconds
          setTimeout(() => setKycMessage(null), 3000);
          break;
        } else if (status === 'rejected') {
          console.log('KYC rejected!');
          setKycStatus('rejected');
          setKycMessage('KYC verification was rejected. Please try again.');
          // Clear error message after 5 seconds
          setTimeout(() => setKycMessage(null), 5000);
          break;
        } else {
          console.log('KYC still pending...');
          // Update status even if pending to ensure UI reflects current state
          setKycStatus(status || 'pending');
        }
        
        // Wait 2 seconds between checks (reduced from 3)
        await new Promise(r => setTimeout(r, 2000));
      } catch (err) {
        console.error(`Error polling KYC status (attempt ${i + 1}):`, err);
        // Don't break on first error, continue polling
        await new Promise(r => setTimeout(r, 2000));
      }
    }
    
    // If we've exhausted all attempts, try one final manual check
    try {
      console.log('Performing final KYC status check...');
      const finalRes = await api.post(`/api/v1/kyc/check-status/${userId}`);
      if (finalRes.data.status === 'success') {
        const finalStatus = finalRes.data.kyc_status;
        console.log('Final KYC status:', finalStatus);
        setKycStatus(finalStatus);
        const updated = { ...accountData, kyc_status: finalStatus };
        setAccountData(updated);
        localStorage.setItem('userData', JSON.stringify(updated));
        
        if (finalStatus === 'approved') {
          setKycMessage('KYC verification completed successfully!');
          setTimeout(() => setKycMessage(null), 3000);
        }
      }
    } catch (err) {
      console.error('Error in final KYC status check:', err);
    }
  };

  const handleKycModalClose = () => {
    console.log('KYC modal closed, starting status check...');
    setKycModalVisible(false);
    
    // Immediately check status once
    if (accountData?.user_id) {
      checkKycStatus(accountData.user_id);
    }
    
    // Add a small delay to allow webhook processing, then start polling
    setTimeout(() => {
      if (accountData?.user_id) {
        pollKycStatus(accountData.user_id);
      }
    }, 2000);
  };

  if (loading) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">-</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center p-4">
        <div className="text-center max-w-md mx-auto">
          <div className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-8 shadow-2xl">
            <div className="mb-6">
              <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <FaTimes className="text-white text-2xl" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-3">Error Loading Wallet</h2>
              <p className="text-zinc-400 leading-relaxed">{error}</p>
            </div>
            <button
              onClick={() => router.push('/')}
              className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
            >
              Go Back to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <SumsubKYCModal
        accessToken={kycAccessToken || ''}
        visible={kycModalVisible}
        onClose={handleKycModalClose}
        applicantEmail={accountData?.email}
      />
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden">
        <WalletHeader 
          accountData={accountData}
          onLogout={handleLogout}
          onMenuToggle={() => setShowMenu(!showMenu)}
        />
        <HamburgerMenu 
          visible={showMenu} 
          onClose={() => setShowMenu(false)}
          onLogout={handleLogout}
          accountData={accountData}
          onCopyAddress={() => copyToClipboard(accountData?.wallet_address || '')}
        />
        <div className="container mx-auto px-4 py-8 max-w-4xl">
          {!accountData?.username && (
            <UsernameCard
              accountData={accountData}
              showUsernameForm={showUsernameForm}
              username={username}
              usernameLoading={usernameLoading}
              usernameError={usernameError}
              usernameSuccess={usernameSuccess}
              setShowUsernameForm={setShowUsernameForm}
              setUsername={setUsername}
              handleSetUsername={handleSetUsername}
              handleCancelUsername={handleCancelUsername}
            />
          )}
          {accountData?.username && (
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-white mb-4">Welcome back</h2>
              <div className="flex items-center justify-center mb-3 gap-2">
                <h3 className="text-2xl font-bold" style={{ color: '#a259f7' }}>
                  @{accountData.username}
                </h3>
                <span className="flex items-center gap-1 bg-green-900/30 text-green-400 text-xs font-semibold px-2 py-1 rounded-full">
                  <FaCheck className="text-green-400 text-base" /> Active
                </span>
              </div>
              <p className="text-zinc-400">
                {kycStatus === 'approved' ? 'Your secure digital wallet is ready' : 'Complete KYC to unlock full wallet functionality'}
              </p>
            </div>
          )}
          <BalanceCard
            balance={balance}
            error={error}
            accountData={accountData}
            showTransactions={showTransactions}
            setShowTransactions={setShowTransactions}
            transactionHistoryRefresh={transactionHistoryRefresh}
            kycStatus={kycStatus}
            onKycClick={() => openKycModal(accountData?.user_id)}
            onRefreshKyc={() => accountData?.user_id && fetchUserData(accountData.user_id)}
            onCheckKycStatus={() => accountData?.user_id && checkKycStatus(accountData.user_id)}
            kycChecking={kycChecking}
            kycMessage={kycMessage}
            onSkipKyc={() => accountData?.user_id && skipKyc(accountData.user_id)}
          />
          {accountData?.username && kycStatus === 'approved' && (
            <div className="flex flex-row gap-4 mb-8 w-full justify-center mt-8">
              <button
                type="button"
                className="flex-1 py-4 px-8 rounded-2xl bg-green-600 text-white text-xl font-bold shadow-lg hover:bg-green-700 hover:scale-[1.03] transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-green-400"
                style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
                onClick={() => {}}
              >
                Create Token
              </button>
              <button
                type="button"
                onClick={() => setShowSendForm(true)}
                className="flex-1 bg-gradient-to-r from-blue-600 to-purple-700 hover:from-blue-700 hover:to-purple-800 text-white py-4 px-8 rounded-2xl font-bold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-xl"
              >
                <FaArrowUp className="mr-3" />
                Pay
              </button>
            </div>
          )}
        </div>
        {showSendForm && (
          <SendUSDCModal
            visible={showSendForm}
            onClose={handleCancelSend}
            receiverUsername={receiverUsername}
            setReceiverUsername={setReceiverUsername}
            sendAmount={sendAmount}
            setSendAmount={setSendAmount}
            sendLoading={sendLoading}
            sendError={sendError}
            sendSuccess={sendSuccess}
            onSend={handleSendUSDC}
          />
        )}
      </div>
    </>
  );
} 