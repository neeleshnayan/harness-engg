"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { hedgeFundApi } from "@/lib/api";
import { SubgraphAnalyticsGeneric } from "../components/SubgraphAnalyticsGeneric";
import { TradingSignals } from "../components/TradingSignals";
import { useYearnWETHConfig } from "@/hooks/useStrategyConfig";
import WalletHeader from "@/components/wallet/WalletHeader";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import { getAuth, signOut } from "firebase/auth";
import { getFirebaseApp } from "@/lib/firebaseClient";
import { Toaster } from "@/components/ui/toaster";
import { TransactionWebhookProvider } from "@/contexts/TransactionWebhookContext";

export default function StrategyDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const strategyId = params.strategyId as string;

  const { data: yearnWethConfig, isLoading: yearnWethConfigLoading } = useYearnWETHConfig();
  const [strategies, setStrategies] = useState<any[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [accountData, setAccountData] = useState<any>(null);
  const [showMenu, setShowMenu] = useState(false);

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        setStrategiesLoading(true);
        const res = await hedgeFundApi.get('/api/v1/strategies');
        if (res.data && res.data.data) {
          setStrategies(res.data.data);
        }
      } catch (e) {
        console.error("Failed to fetch strategies", e);
      } finally {
        setStrategiesLoading(false);
      }
    };
    fetchStrategies();

    const storedUserData = localStorage.getItem('userData');
    if (storedUserData) {
      try {
        setAccountData(JSON.parse(storedUserData));
      } catch { /* corrupted userData */ }
    }
  }, []);

  const handleLogout = async () => {
      try {
        const app = getFirebaseApp();
        if (app) {
          const auth = getAuth(app);
          await signOut(auth);
        }
        localStorage.removeItem('userData');
        router.push('/');
      } catch (err) {
        console.error('Error logging out:', err);
      }
    };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      // Fallback
      console.error('Failed to copy', err);
    }
  };

  const currentStrategy = useMemo(() => {
      if (!strategies.length) return null;
      // Try to find by ID first, then Symbol if ID doesn't match
      return strategies.find(s => s.id === strategyId || s.symbol === strategyId) || 
             (strategyId === 'YEARN_WETH' ? strategies.find(s => s.id === 'YEARN_WETH') : null);
  }, [strategies, strategyId]);

  if (strategiesLoading || (strategyId === 'YEARN_WETH' && yearnWethConfigLoading)) {
    return (
      <div className="min-h-screen w-full bg-[#001C1B] dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">Loading strategy details...</p>
        </div>
      </div>
    );
  }

  if (!currentStrategy && !strategiesLoading) {
      return (
          <div className="min-h-screen w-full bg-[#001C1B] dark flex flex-col items-center justify-center p-4">
              <h1 className="text-2xl text-white mb-4">Strategy Not Found</h1>
              <button
                  onClick={() => router.back()}
                  className="bg-zinc-800 text-white px-6 py-2 rounded-xl"
              >
                  Go back
              </button>
          </div>
      );
  }

  const displayName = currentStrategy?.name || "Strategy Details";
  // Fallback to config or env for plain YEARN_WETH if needed, but currentStrategy should have it
  const subgraphUrl = currentStrategy?.subgraph_url || yearnWethConfig?.subgraph_url || process.env.NEXT_PUBLIC_SUBGRAPH_URL;
  const stratNameKey = currentStrategy?.id || "YEARN_WETH";

  return (
    <TransactionWebhookProvider walletAddress={accountData?.wallet_address}>
      <Toaster />
      <div className="min-h-screen w-full bg-[#001C1B] dark overflow-x-hidden">
        <WalletHeader
          accountData={accountData}
          onLogout={handleLogout}
          onMenuToggle={() => setShowMenu(!showMenu)}
          onOpenQuestionnaire={() => {}} // No-op here or implement if needed
        />
        <HamburgerMenu
          visible={showMenu}
          onClose={() => setShowMenu(false)}
          onLogout={handleLogout}
          accountData={accountData}
          onCopyAddress={() => copyToClipboard(accountData?.wallet_address || '')}
        />

        <div className="container mx-auto px-4 py-5 sm:py-6 max-w-7xl">
          <div className="mb-4 sm:mb-5 px-4">
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-1 drop-shadow-lg leading-tight">
              {displayName}
            </h1>
            <p className="text-zinc-400 text-sm sm:text-base md:text-lg max-w-3xl leading-snug">
              {currentStrategy?.description || "Real-time on-chain analytics and trading data."}
            </p>
          </div>

          <div className="mb-4">
            <TradingSignals
              strategyName={stratNameKey}
              assetSymbol="USDC"
              targetSymbol={currentStrategy?.symbol || "WETH"}
              assetAddress={currentStrategy?.asset_address}
              targetAddress={currentStrategy?.target_address}
            />
          </div>

          <SubgraphAnalyticsGeneric
            subgraphUrl={subgraphUrl}
            strategyAddress={currentStrategy?.address}
            poolAddress={currentStrategy?.pool_address}
            strategyName={displayName}
            assetSymbol="USDC"
            targetSymbol={currentStrategy?.symbol}
            underlyingSymbol={currentStrategy?.underlying_symbol || currentStrategy?.symbol?.replace(/^(YS|KP|KF)/, '')}
            targetTokenDecimals={currentStrategy?.target_decimals ?? 6}
            aumDecimals={currentStrategy?.aum_decimals ?? (currentStrategy?.symbol?.includes('SILVER') || currentStrategy?.symbol?.includes('GOLD') ? 8 : 0)}
          />
        </div>
      </div>
    </TransactionWebhookProvider>
  );
}
