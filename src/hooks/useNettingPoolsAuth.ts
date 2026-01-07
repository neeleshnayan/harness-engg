import { useState, useEffect } from 'react';

interface UserData {
  user_id: string;
  username?: string;
  wallet_address: string;
  email: string;
}

export function useNettingPoolsAuth() {
  const [userData, setUserData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedData = localStorage.getItem('userData');
    if (storedData) {
      try {
        const parsed = JSON.parse(storedData);
        setUserData(parsed);
      } catch (err) {
        console.error('Failed to parse user data:', err);
      }
    }
    setLoading(false);
  }, []);

  return {
    userData,
    username: userData?.username || userData?.email || '',
    walletAddress: userData?.wallet_address || '',
    isAuthenticated: !!userData,
    loading,
  };
}

