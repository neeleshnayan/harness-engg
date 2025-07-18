'use client';

import React, { useState, useEffect } from "react";
import { getAuth, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import { FaWallet, FaSignOutAlt, FaCopy, FaArrowUp, FaArrowDown, FaUser, FaCheck, FaTimes, FaBars } from "react-icons/fa";
import { getFirebaseApp } from "@/lib/firebaseClient";
import UsernameCard from "@/components/wallet/UsernameCard";
import BalanceCard from "@/components/wallet/BalanceCard";
import SendUSDCModal from "@/components/wallet/SendUSDCModal";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import QuickActions from "@/components/wallet/QuickActions";
import api from "@/lib/api";
import TransakWidgetModal from "@/components/wallet/TransakWidgetModal";
import WalletHeader from "@/components/wallet/WalletHeader";


export default function WalletPage() {
  const [accountData, setAccountData] = useState<any>(null);
  const [balance, setBalance] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState<string>("");
  const [showUsernameForm, setShowUsernameForm] = useState(false);
  const [usernameLoading, setUsernameLoading] = useState(false);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [usernameSuccess, setUsernameSuccess] = useState<string | null>(null);
  
  // Send USDC states
  const [showSendForm, setShowSendForm] = useState(false);
  const [receiverUsername, setReceiverUsername] = useState<string>("");
  const [sendAmount, setSendAmount] = useState<string>("");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  
  // Hamburger menu states
  const [showMenu, setShowMenu] = useState(false);
  
  // Transaction history states
  const [showTransactions, setShowTransactions] = useState(false);
  
  const [refreshingBalance, setRefreshingBalance] = useState(false);
  const [showTransakModal, setShowTransakModal] = useState(false);
  
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
    let didTimeout = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      didTimeout = true;
      controller.abort();
      setError('Could not load balance. Please try again.');
    }, 10000); // 10s timeout
    try {
      const res = await api.get(`/api/v1/wallet_balance/${walletAddress}`, { signal: controller.signal });
      if (!didTimeout) {
        setBalance(res.data);
        setRefreshingBalance(false); // Done refreshing
      }
    } catch (err) {
      if (!didTimeout) {
        setError('Could not load balance. Please try again.');
        setRefreshingBalance(false); // Done refreshing (even on error)
      }
    } finally {
      clearTimeout(timeout);
    }
  };

  const handleLogout = async () => {
    console.log('Sign out clicked');
    try {
      const app = getFirebaseApp();
      if (app) {
        const auth = getAuth(app);
        await signOut(auth);
      }
      localStorage.removeItem('userData');
      setShowMenu(false); // Close the menu
      setTimeout(() => router.replace('/'), 150); // Use replace for hard navigation
    } catch (err) {
      console.error('Error signing out:', err);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      console.log('Copied to clipboard:', text);
      // You could add a toast notification here
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      // Fallback for older browsers
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
      // Update the account data to include the username
      const updatedAccountData = {
        ...accountData,
        username: cleanUsername.trim()
      };
      setAccountData(updatedAccountData);
      localStorage.setItem('userData', JSON.stringify(updatedAccountData));
    } catch (err: any) {
      setUsernameError(err.response?.data?.detail || "Failed to set username");
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
      setRefreshingBalance(true); // Start refreshing
      if (accountData.wallet_address) {
        fetchBalance(accountData.wallet_address);
      }
    } catch (err: any) {
      setSendError(err.response?.data?.detail || "Failed to send USDC");
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

  if (loading) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">Loading your wallet...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center p-4">
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
    <>
      <WalletHeader
        showMenu={showMenu}
        setShowMenu={setShowMenu}
        onBuyCrypto={() => setShowTransakModal(true)}
      />
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex flex-col">
        {/* Main Content - vertically distributed */}
        <main className="flex flex-col flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 pt-2 pb-0">
          {accountData?.username ? (
            // Layout when username is set up - center balance, evenly space others
            <div className="flex flex-col flex-1 min-h-[70vh] justify-between">
              {/* Welcome Section */}
              <div className="text-center mt-12 mb-10">
                <h2 className="text-3xl font-bold text-white mb-4">Welcome back</h2>
                <div className="flex items-center justify-center mb-3 gap-2">
                  <h3 className="text-2xl font-bold" style={{ color: '#a259f7' }}>
                    @{accountData.username}
                  </h3>
                  <span className="flex items-center gap-1 bg-green-900/30 text-green-400 text-xs font-semibold px-2 py-1 rounded-full">
                    <FaCheck className="text-green-400 text-base" /> Active
                  </span>
                </div>
                <p className="text-zinc-400">Your secure digital wallet is ready</p>
              </div>

              {/* Balance Card - Centered with more space */}
              <div className="flex-1 flex items-center justify-center mb-10">
                <BalanceCard
                  balance={balance}
                  error={error}
                  accountData={accountData}
                  showTransactions={showTransactions}
                  setShowTransactions={setShowTransactions}
                  className="w-full max-w-xl mx-auto"
                />
              </div>

              {/* Quick Actions - Bottom with more space */}
              <div className="flex justify-center w-full mb-12 mt-4">
                <div className="w-full max-w-md">
                  <QuickActions setShowSendForm={setShowSendForm} payLabel="Pay" />
                </div>
              </div>
            </div>
          ) : (
            // Layout when username is not set up - original layout
            <div className="flex flex-col gap-y-2">
              {/* Welcome Section */}
              <div className="text-center mt-12 sm:mt-12 mb-2">
                <h2 className="text-3xl font-bold text-white mb-2">Welcome back</h2>
                <div className="flex items-center justify-center mb-2 gap-2">
                  <h3 className="text-2xl font-bold text-zinc-200">
                    {accountData?.email}
                  </h3>
                  <span className="flex items-center gap-1 bg-red-900/30 text-red-400 text-xs font-semibold px-2 py-1 rounded-full">
                    <FaTimes className="text-red-400 text-base" /> Inactive
                  </span>
                </div>
                <p className="text-zinc-400">Set a username to activate your wallet and receive payments.</p>
              </div>

              {/* Username Card */}
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

              {/* Balance Card */}
              <BalanceCard
                balance={balance}
                error={error}
                accountData={accountData}
                showTransactions={showTransactions}
                setShowTransactions={setShowTransactions}
                className="w-full max-w-xl mx-auto my-2"
              />

              {/* Quick Actions */}
              <div className="mt-4 mb-4 flex justify-center w-full">
                <div className="w-full max-w-md">
                  <QuickActions setShowSendForm={setShowSendForm} payLabel="Pay" />
                </div>
              </div>
            </div>
          )}

          {/* Send USDC Modal */}
          <SendUSDCModal
            showSendForm={showSendForm}
            receiverUsername={receiverUsername}
            setReceiverUsername={setReceiverUsername}
            sendAmount={sendAmount}
            setSendAmount={setSendAmount}
            sendLoading={sendLoading}
            sendError={sendError}
            sendSuccess={sendSuccess}
            handleSendUSDC={handleSendUSDC}
            handleCancelSend={handleCancelSend}
            refreshingBalance={refreshingBalance}
          />
        </main>

        {/* Footer */}
        <footer className="w-full py-2 flex flex-col justify-center items-center border-t border-zinc-800 mt-auto">
          <span className="text-zinc-500 text-sm">Secure • Fast • Reliable</span>
          <span className="text-zinc-600 text-xs mt-1">© {new Date().getFullYear()} Krypton Fund LLC</span>
        </footer>

        <HamburgerMenu 
          showMenu={showMenu} 
          setShowMenu={setShowMenu} 
          handleLogout={handleLogout}
          accountData={accountData}
          copyToClipboard={copyToClipboard}
        />
      </div>
      <TransakWidgetModal open={showTransakModal} onClose={() => setShowTransakModal(false)} />
    </>
  );
} 
