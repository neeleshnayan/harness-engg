"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { SubgraphAnalyticsMAVP } from "@/components/wallet/SubgraphAnalyticsMAVP";
import { useMAVPConfig } from "@/hooks/useMAVPConfig";

export default function MAVPDetailPage() {
  const router = useRouter();
  const { data: mavpConfig, isLoading: configLoading } = useMAVPConfig();

  console.log('🔍 MAVP Config Debug:', {
    mavpConfig,
    subgraph_url: mavpConfig?.subgraph_url,
    configLoading
  });

  return (
    <div className="min-h-screen w-full flex flex-col bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
      <div className="container mx-auto max-w-7xl">
        <div className="flex justify-between items-start mb-8">
          <button
            onClick={() => router.push('/customer/grow/hedge-fund-v2')}
            className="bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-sm flex items-center"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Strategies
          </button>
        </div>

        <div className="mb-8">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-2 drop-shadow-lg">
            Multi Asset Vault Protocol (MAVP)
          </h1>
          <p className="text-zinc-400 text-lg max-w-3xl">
            Real-time on-chain analytics and subgraph data for the Multi Asset Vault Protocol strategy.
          </p>
        </div>

        {configLoading ? (
          <div className="text-center text-zinc-400">Loading configuration...</div>
        ) : (
          <SubgraphAnalyticsMAVP subgraphUrl={mavpConfig?.subgraph_url} />
        )}
      </div>
    </div>
  );
}

