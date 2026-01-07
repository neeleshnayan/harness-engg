'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Dashboard from '@/components/pools/Dashboard';

export default function LiquidityPoolsPage() {
  const router = useRouter();

  useEffect(() => {
    // Check if user is authenticated
    const userData = localStorage.getItem('userData');
    if (!userData) {
      router.push('/');
      return;
    }
  }, [router]);

  return (
    <div className="min-h-screen bg-black">
      <Dashboard />
    </div>
  );
}

