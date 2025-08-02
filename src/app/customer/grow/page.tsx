"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Shield, Store } from "lucide-react";

export default function CustomerGrowPage() {
  const router = useRouter();
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
      <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
        Grow Your Wealth
      </h1>
      <p className="text-zinc-400 text-lg mb-12 text-center max-w-xl">
        Explore exclusive investment opportunities tailored for you.
      </p>
      <div className="flex flex-col md:flex-row gap-8 w-full max-w-3xl justify-center">
        <button
          className="flex-1 bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-cyan-400/10 hover:border-cyan-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-cyan-400"
          style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
          onClick={() => router.push('/customer/grow/hedge-fund')}
        >
          <div className="w-16 h-16 rounded-full bg-cyan-400/20 flex items-center justify-center mb-6 group-hover:bg-cyan-400/30 transition-all">
            <Shield className="h-10 w-10 text-cyan-300 group-hover:text-cyan-400 transition-all" />
          </div>
          <span className="text-2xl font-bold text-white mb-2">Hedge Fund</span>
          <span className="text-zinc-400 text-base text-center">
            Access actively managed investment strategies to help grow and protect your assets.
          </span>
        </button>
        <button
          className="flex-1 bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-fuchsia-400/10 hover:border-fuchsia-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
          style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
          onClick={() => router.push('/customer/grow/marketplace')}
        >
          <div className="w-16 h-16 rounded-full bg-fuchsia-400/20 flex items-center justify-center mb-6 group-hover:bg-fuchsia-400/30 transition-all">
            <Store className="h-10 w-10 text-fuchsia-300 group-hover:text-fuchsia-400 transition-all" />
          </div>
          <span className="text-2xl font-bold text-white mb-2">Private Marketplace</span>
          <span className="text-zinc-400 text-base text-center">
            Discover exclusive deals and private market assets not available to the public.
          </span>
        </button>
      </div>
    </div>
  );
} 